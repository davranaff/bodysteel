import secrets
from dataclasses import dataclass
from datetime import timedelta
from html import escape

from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone

from customer_telegram.bot_api import CustomerTelegramApi, DeliveryStatus
from customer_telegram.configuration import require_configuration
from customer_telegram.delivery_limits import reserve_marketing_slot
from customer_telegram.models import (
    CustomerTelegramCampaign,
    CustomerTelegramCampaignRecipient,
    CustomerTelegramChat,
)


RETRY_DELAYS = (60, 300, 1_800, 7_200, 21_600)
LEASE_TIMEOUT = timedelta(minutes=5)

@dataclass
class CampaignSummary:
    delivered: int = 0
    retried: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0

def queue_due_campaigns(limit=20, now=None):
    current = now or timezone.now()
    due = CustomerTelegramCampaign.objects.filter(
        Q(status=CustomerTelegramCampaign.QUEUEING)
        | Q(status=CustomerTelegramCampaign.SCHEDULED, scheduled_at__lte=current)
    ).order_by('scheduled_at', 'created_at').values_list('pk', flat=True)[:limit]
    for campaign_id in due:
        build_campaign_audience(campaign_id, current)


def build_campaign_audience(campaign_id, now=None):
    current = now or timezone.now()
    configuration = require_configuration()
    if not configuration.campaigns_enabled:
        return 0
    with transaction.atomic():
        campaign = CustomerTelegramCampaign.objects.select_for_update().get(pk=campaign_id)
        if campaign.status not in {
            CustomerTelegramCampaign.QUEUEING, CustomerTelegramCampaign.SCHEDULED,
        }:
            return campaign.recipient_count
        if campaign.status == CustomerTelegramCampaign.SCHEDULED and (
            campaign.scheduled_at is None or campaign.scheduled_at > current
        ):
            return campaign.recipient_count
        campaign.full_clean()
        campaign.status = CustomerTelegramCampaign.QUEUEING
        campaign.save(update_fields=('status', 'updated_at'))
    chats = CustomerTelegramChat.objects.filter(
        is_active=True, marketing_opt_in=True, blocked_at__isnull=True,
    ).only('pk', 'language')
    batch = []
    for chat in chats.iterator(chunk_size=500):
        language = chat.language if chat.language in {'ru', 'uz'} else 'ru'
        batch.append(_recipient(campaign, chat, language, current))
        if len(batch) == 500:
            CustomerTelegramCampaignRecipient.objects.bulk_create(batch, ignore_conflicts=True)
            batch = []
    if batch:
        CustomerTelegramCampaignRecipient.objects.bulk_create(batch, ignore_conflicts=True)
    with transaction.atomic():
        campaign = CustomerTelegramCampaign.objects.select_for_update().get(pk=campaign_id)
        count = campaign.recipients.count()
        campaign.recipient_count = count
        campaign.audience_built_at = current
        campaign.started_at = campaign.started_at or current
        campaign.status = CustomerTelegramCampaign.SENDING if count else CustomerTelegramCampaign.COMPLETED
        campaign.completed_at = None if count else current
        campaign.save(update_fields=(
            'recipient_count', 'audience_built_at', 'started_at', 'status',
            'completed_at', 'updated_at',
        ))
    return count


def deliver_campaign_batch(limit=100, api=None, now=None):
    configuration = require_configuration()
    if not configuration.campaigns_enabled:
        return CampaignSummary()
    current = now or timezone.now()
    queue_due_campaigns(now=current)
    client = api or CustomerTelegramApi()
    summary = CampaignSummary()
    for _ in range(limit):
        recipient = _claim_recipient(current)
        if not recipient:
            break
        outcome = _deliver_recipient(recipient, client, current)
        setattr(summary, outcome, getattr(summary, outcome) + 1)
    return summary


def send_test_campaign(campaign, chat, api=None):
    if not require_configuration().campaigns_enabled:
        return False
    if (not chat or not chat.is_active or not chat.marketing_opt_in
            or chat.blocked_at is not None):
        return False
    campaign.full_clean()
    if reserve_marketing_slot(chat.pk, timezone.now()).status != 'ready':
        return False
    language = chat.language if chat.language in {'ru', 'uz'} else 'ru'
    recipient = _recipient(campaign, chat, language, timezone.now())
    result = (api or CustomerTelegramApi()).send_message(
        chat.chat_id,
        _message_text(recipient),
        _button_markup(recipient),
    )
    return result.status is DeliveryStatus.SENT


def _claim_recipient(now):
    stale = now - LEASE_TIMEOUT
    due = Q(status__in=('pending', 'retry'), next_attempt_at__lte=now) | Q(
        status='sending', locked_at__lte=stale,
    ) | Q(status='sending', locked_at__isnull=True)
    with transaction.atomic():
        queryset = CustomerTelegramCampaignRecipient.objects.filter(
            due, campaign__status=CustomerTelegramCampaign.SENDING,
        ).select_related('chat', 'campaign').order_by('next_attempt_at', 'created_at')
        queryset = queryset.select_for_update(of=('self',), skip_locked=True) if (
            connection.features.has_select_for_update_skip_locked
        ) else queryset.select_for_update(of=('self',))
        recipient = queryset.first()
        if not recipient:
            return None
        recipient.status = CustomerTelegramCampaignRecipient.SENDING
        recipient.attempt_count += 1
        recipient.lease_token = secrets.token_hex(16)
        recipient.locked_at = now
        recipient.failure_code = ''
        recipient.save(update_fields=(
            'status', 'attempt_count', 'lease_token', 'locked_at', 'failure_code', 'updated_at',
        ))
        return recipient


def _deliver_recipient(recipient, api, now):
    chat = recipient.chat
    if not chat.is_active or not chat.marketing_opt_in or chat.blocked_at is not None:
        _finish(recipient, CustomerTelegramCampaignRecipient.SKIPPED, now, 'opted_out')
        return 'skipped'
    slot = reserve_marketing_slot(chat.pk, now)
    if slot.status == 'inactive':
        _finish(recipient, CustomerTelegramCampaignRecipient.SKIPPED, now, 'opted_out')
        return 'skipped'
    if slot.status == 'wait':
        _retry(recipient, slot.retry_at, 'chat_throttled')
        return 'retried'
    result = api.send_message(chat.chat_id, _message_text(recipient), _button_markup(recipient))
    if result.status is DeliveryStatus.SENT:
        _finish(recipient, CustomerTelegramCampaignRecipient.DELIVERED, now, '', result.message_id)
        return 'delivered'
    if result.status is DeliveryStatus.BLOCKED:
        _block_chat(recipient, now)
        _finish(recipient, CustomerTelegramCampaignRecipient.BLOCKED, now, 'bot_blocked')
        return 'blocked'
    if result.status in {DeliveryStatus.UNKNOWN, DeliveryStatus.RATE_LIMITED}:
        if recipient.attempt_count <= len(RETRY_DELAYS):
            base = RETRY_DELAYS[recipient.attempt_count - 1]
            delay = max(base, result.retry_after or 0)
            _retry(recipient, now + timedelta(seconds=delay), 'transient')
            return 'retried'
        _finish(recipient, CustomerTelegramCampaignRecipient.FAILED, now, 'retry_exhausted')
        return 'failed'
    _finish(recipient, CustomerTelegramCampaignRecipient.FAILED, now, 'permanent_error')
    return 'failed'


def _finish(recipient, status, now, failure_code, message_id=None):
    _leased(recipient).update(
        status=status, failure_code=failure_code, telegram_message_id=message_id,
        delivered_at=now if status == 'delivered' else None, lease_token=None, locked_at=None,
    )
    _refresh_campaign(recipient.campaign_id, now)


def _retry(recipient, next_attempt_at, failure_code):
    _leased(recipient).update(
        status=CustomerTelegramCampaignRecipient.RETRY,
        next_attempt_at=next_attempt_at,
        failure_code=failure_code,
        lease_token=None,
        locked_at=None,
    )


def _leased(recipient):
    return CustomerTelegramCampaignRecipient.objects.filter(
        pk=recipient.pk,
        status=CustomerTelegramCampaignRecipient.SENDING,
        lease_token=recipient.lease_token,
    )


def _refresh_campaign(campaign_id, now):
    with transaction.atomic():
        campaign = CustomerTelegramCampaign.objects.select_for_update().get(pk=campaign_id)
        counts = {row['status']: row['count'] for row in campaign.recipients.values(
            'status',
        ).annotate(count=Count('id'))}
        campaign.delivered_count = counts.get('delivered', 0)
        campaign.failed_count = counts.get('failed', 0)
        campaign.blocked_count = counts.get('blocked', 0)
        active = sum(counts.get(status, 0) for status in ('pending', 'retry', 'sending'))
        if not active:
            campaign.status = CustomerTelegramCampaign.COMPLETED
            campaign.completed_at = now
        campaign.save(update_fields=(
            'delivered_count', 'failed_count', 'blocked_count', 'status',
            'completed_at', 'updated_at',
        ))


def _recipient(campaign, chat, language, now):
    suffix = 'ru' if language == 'ru' else 'uz'
    return CustomerTelegramCampaignRecipient(
        campaign=campaign, chat=chat, language=language,
        rendered_title=getattr(campaign, 'title_{}'.format(suffix)),
        rendered_body=getattr(campaign, 'body_{}'.format(suffix)),
        rendered_button_text=getattr(campaign, 'button_text_{}'.format(suffix)),
        rendered_button_url=campaign.button_url, next_attempt_at=now,
    )
def _message_text(recipient):
    return '<b>{}</b>\n\n{}'.format(escape(recipient.rendered_title), escape(recipient.rendered_body))
def _button_markup(recipient):
    if not recipient.rendered_button_text:
        return None
    return {'inline_keyboard': [[{
        'text': recipient.rendered_button_text,
        'url': recipient.rendered_button_url,
    }]]}
def _block_chat(recipient, now):
    CustomerTelegramChat.objects.filter(pk=recipient.chat_id).update(
        is_active=False, blocked_at=now, marketing_opt_in=False,
        marketing_opted_out_at=now, updated_at=now,
    )
