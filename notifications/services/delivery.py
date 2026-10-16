import hmac
import secrets
import uuid
from datetime import timedelta

from cryptography.fernet import InvalidToken
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.authtoken.models import Token

from notifications.clients.firebase import FirebaseSender
from notifications.configuration import PushNotConfigured, require_provider_configuration, token_cipher
from notifications.models import PushCampaign, PushDelivery, PushDevice
from notifications.services.campaigns import require_permission
from notifications.services.devices import credential_digest

MAX_ATTEMPTS = 5
LEASE_SECONDS = 300
ORDER_UPDATE_MAX_AGE_HOURS = 24


def due_deliveries(now):
    due = Q(status__in=('pending', 'retry'), next_attempt_at__lte=now)
    due |= Q(status='sending', locked_at__lte=now - timedelta(seconds=LEASE_SECONDS))
    campaigns = Q(is_test=True, campaign__status='draft') | Q(
        campaign__status__in=('queued', 'scheduled', 'sending'))
    released = Q(is_test=True) | Q(campaign__scheduled_at__isnull=True) | Q(campaign__scheduled_at__lte=now)
    sources = Q(kind=PushDelivery.Kind.CAMPAIGN) & campaigns & released
    sources |= Q(kind=PushDelivery.Kind.ORDER_UPDATE)
    return PushDelivery.objects.filter(due).filter(sources)


def deliver_pending(limit=100, sender=None, now=None):
    require_provider_configuration()
    current = now or timezone.now()
    provider = sender or FirebaseSender()
    due_deliveries(current).filter(attempt_count__gte=MAX_ATTEMPTS).update(status='failed', failure_code='attempts_exhausted')
    identifiers = list(due_deliveries(current).filter(attempt_count__lt=MAX_ATTEMPTS).order_by('next_attempt_at', 'pk').values_list('pk', flat=True)[:limit])
    processed = 0
    for identifier in identifiers:
        current = now or timezone.now()
        lease = uuid.uuid4()
        claimed = due_deliveries(current).filter(pk=identifier, attempt_count__lt=MAX_ATTEMPTS).update(
            status='sending', lease_token=lease, locked_at=current, attempt_count=F('attempt_count') + 1)
        if not claimed:
            continue
        delivery = PushDelivery.objects.select_related('device__user', 'campaign', 'order').get(pk=identifier)
        if delivery.kind == PushDelivery.Kind.CAMPAIGN and not delivery.is_test:
            PushCampaign.objects.filter(pk=delivery.campaign_id, status__in=('queued', 'scheduled')).update(status='sending')
        _deliver(delivery, lease, provider, current)
        processed += 1
    _complete_campaigns(current)
    return processed


def _deliver(delivery, lease, sender, now):
    device = delivery.device
    if delivery.kind == PushDelivery.Kind.ORDER_UPDATE:
        reason = _order_skip_reason(delivery, now)
    else:
        reason = _campaign_skip_reason(delivery)
    if reason:
        return _finish(delivery, lease, 'skipped', reason)
    marketing = delivery.kind == PushDelivery.Kind.CAMPAIGN and not delivery.is_test
    if (device is None or not device.is_active or device.user_id != delivery.user_id
            or device.registration_scope != delivery.expected_scope or not device.user.is_active
            or device.user.deleted_at is not None or device.permission not in ('authorized', 'provisional')
            or (marketing and not device.marketing_opt_in)
            or device.last_seen_at < now - timedelta(days=settings.PUSH_DEVICE_STALE_DAYS)):
        return _finish(delivery, lease, 'skipped', 'device_ineligible')
    credential = Token.objects.filter(user_id=device.user_id).first()
    if credential is None or not hmac.compare_digest(device.credential_digest, credential_digest(device.user_id, credential.key)):
        return _finish(delivery, lease, 'skipped', 'session_revoked')
    try:
        token = token_cipher().decrypt(device.token_ciphertext.encode()).decode()
    except (InvalidToken, UnicodeError):
        return _finish(delivery, lease, 'failed', 'token_key_unavailable')
    try:
        result = sender.send(token, delivery)
    except PushNotConfigured:
        return _finish(delivery, lease, 'retry', 'provider_not_configured', next_attempt_at=now + timedelta(minutes=10))
    if result.outcome == 'accepted':
        return _finish(delivery, lease, 'accepted', '', accepted_at=now, provider_message_id=result.message_id[:255])
    if result.outcome == 'invalid_token':
        # Never deactivate a refreshed token or a new owner after an in-flight send.
        PushDevice.objects.filter(pk=device.pk, token_digest=device.token_digest,
                                  registration_scope=delivery.expected_scope).update(is_active=False)
        return _finish(delivery, lease, 'failed', result.code)
    if result.outcome == 'retry' and delivery.attempt_count < MAX_ATTEMPTS:
        delay = max(result.retry_after, 30 * 2 ** delivery.attempt_count) + secrets.randbelow(16)
        return _finish(delivery, lease, 'retry', result.code, next_attempt_at=now + timedelta(seconds=delay))
    return _finish(delivery, lease, 'failed', result.code or 'provider_rejected')


def _campaign_skip_reason(delivery):
    if delivery.campaign is None or delivery.campaign.status == 'cancelled':
        return 'campaign_cancelled'
    operator = delivery.requested_by
    try:
        if not operator:
            raise PermissionDenied()
        require_permission(operator, 'test' if delivery.is_test else 'publish')
    except PermissionDenied:
        return 'publisher_unavailable'
    return ''


def _order_skip_reason(delivery, now):
    # Transactional alerts need no operator or marketing consent, but must still be about
    # the recipient's own, still existing order and not arrive long after the change.
    order = delivery.order
    if order is None or order.user_id is None or order.user_id != delivery.user_id:
        return 'order_unavailable'
    if delivery.created_at < now - timedelta(hours=ORDER_UPDATE_MAX_AGE_HOURS):
        return 'expired'
    return ''


def _finish(delivery, lease, status, code, **values):
    return PushDelivery.objects.filter(pk=delivery.pk, status='sending', lease_token=lease).update(
        status=status, failure_code=code, lease_token=None, locked_at=None, **values)


def _complete_campaigns(now):
    # Order updates have no campaign and never affect campaign completion.
    active = PushCampaign.objects.filter(status__in=('queued', 'scheduled', 'sending'))
    for campaign in active.iterator(chunk_size=100):
        if not campaign.deliveries.filter(is_test=False, status__in=('pending', 'retry', 'sending')).exists():
            PushCampaign.objects.filter(pk=campaign.pk, status__in=('queued', 'scheduled', 'sending')).update(status='completed', completed_at=now)
