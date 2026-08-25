import uuid
from dataclasses import dataclass
from html import escape

from django.db import transaction
from django.utils import timezone

from customer_telegram.bot_api import CustomerTelegramApi, DeliveryStatus
from customer_telegram.i18n import message
from customer_telegram.links import bind_chat_to_user
from customer_telegram.models import CustomerTelegramLink
from store.utils.format_phone import format_phone_number
from users.auth.security import auth_challenge_digest, otp_digest
from users.auth.errors import AuthProblem
from users.auth.rate_limits import CUSTOMER_TELEGRAM_LINK, consume
from users.utils.random_code import random_code


@dataclass(frozen=True)
class OtpOutcome:
    status: str
    language: str = 'ru'


def process_contact(link_id, sender_id, chat_id, contact, api=None):
    return _prepare_and_send(link_id, sender_id, chat_id, contact, True, api)


def deliver_linked_reset(link_id, sender_id, chat_id, api=None):
    return _prepare_and_send(link_id, sender_id, chat_id, None, False, api)


def _prepare_and_send(link_id, sender_id, chat_id, contact, require_contact, api):
    try:
        consume(CUSTOMER_TELEGRAM_LINK, 'contact:{}'.format(link_id))
    except AuthProblem:
        return OtpOutcome('invalid')
    phone = None
    if require_contact:
        contact_user_id = contact.get('user_id') if isinstance(contact, dict) else None
        raw_phone = contact.get('phone_number') if isinstance(contact, dict) else None
        if contact_user_id != sender_id or not isinstance(raw_phone, str):
            return _contact_failure(link_id, sender_id, chat_id)
        phone = _canonical_phone(raw_phone)
        if phone is None:
            return _contact_failure(link_id, sender_id, chat_id)
    now = timezone.now()
    with transaction.atomic():
        link = CustomerTelegramLink.objects.select_for_update(of=('self',)).select_related(
            'chat', 'registration_challenge', 'auth_challenge__user', 'user',
        ).filter(pk=link_id).first()
        if not _valid_open_link(link, sender_id, chat_id, now):
            return OtpOutcome('invalid')
        target_user, expected_phone = _target(link)
        if require_contact and (expected_phone is None or phone != expected_phone):
            return _consume_contact_attempt(link)
        if not require_contact and (
            link.purpose != CustomerTelegramLink.PASSWORD_RESET
            or target_user is None or link.chat.user_id != target_user.pk
        ):
            return OtpOutcome('invalid', link.language)
        if link.purpose == CustomerTelegramLink.ACCOUNT_LINK:
            bind_chat_to_user(link.chat, target_user, now)
            link.state = CustomerTelegramLink.CONSUMED
            link.consumed_at = now
            link.save(update_fields=('state', 'consumed_at', 'updated_at'))
            return OtpOutcome('linked', link.language)
        if target_user is not None:
            bind_chat_to_user(link.chat, target_user, now)
        code, delivery_id = random_code(6), uuid.uuid4()
        if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
            return OtpOutcome('failed', link.language)
        challenge = link.registration_challenge or link.auth_challenge
        challenge.delivery_id = delivery_id
        challenge.code_digest = (
            otp_digest(challenge.pk, delivery_id, code)
            if link.purpose == CustomerTelegramLink.REGISTRATION
            else auth_challenge_digest(challenge.pk, delivery_id, code)
        )
        challenge.status = 'pending'
        challenge.sent_at = None
        challenge.save(update_fields=('delivery_id', 'code_digest', 'status', 'sent_at', 'updated_at'))
        link.state = CustomerTelegramLink.DELIVERING
        link.save(update_fields=('state', 'updated_at'))
        language, target_chat = link.language, link.chat.chat_id
    text = '{}\n<code>{}</code>\n{}'.format(
        message(language, 'otp_title'), escape(code), message(language, 'otp_warning'),
    )
    result = (api or CustomerTelegramApi()).send_message(target_chat, text)
    recorded = _record_delivery(link_id, delivery_id, result.status, now)
    if not recorded:
        return OtpOutcome('invalid', language)
    outcome = 'delivered' if result.status in {DeliveryStatus.SENT, DeliveryStatus.UNKNOWN} else 'failed'
    return OtpOutcome(outcome, language)


def _record_delivery(link_id, delivery_id, status, now):
    delivered = status in {DeliveryStatus.SENT, DeliveryStatus.UNKNOWN}
    challenge_status = 'sent' if status is DeliveryStatus.SENT else 'unknown' if delivered else 'failed'
    with transaction.atomic():
        link = CustomerTelegramLink.objects.select_for_update(of=('self',)).select_related(
            'chat',
        ).get(pk=link_id)
        challenge = link.registration_challenge or link.auth_challenge
        if link.state != CustomerTelegramLink.DELIVERING:
            return False
        updated = type(challenge).objects.filter(
            pk=challenge.pk, delivery_id=delivery_id, status='pending',
        ).update(status=challenge_status, sent_at=now if status is DeliveryStatus.SENT else None)
        if not updated:
            return False
        link.state = CustomerTelegramLink.DELIVERED if delivered else CustomerTelegramLink.FAILED
        link.save(update_fields=('state', 'updated_at'))
        if status is DeliveryStatus.BLOCKED and link.chat_id:
            link.chat.is_active = False
            link.chat.blocked_at = now
            link.chat.marketing_opt_in = False
            link.chat.marketing_opted_out_at = now
            link.chat.save(update_fields=(
                'is_active', 'blocked_at', 'marketing_opt_in', 'marketing_opted_out_at', 'updated_at',
            ))
        return True


def _target(link):
    if link.purpose == CustomerTelegramLink.REGISTRATION:
        return None, link.registration_challenge.phone
    user = link.user if link.purpose == CustomerTelegramLink.ACCOUNT_LINK else link.auth_challenge.user
    if user is None or not user.is_active or user.deleted_at is not None:
        return None, None
    return user, user.phone


def _valid_open_link(link, sender_id, chat_id, now):
    return bool(
        link and link.state == CustomerTelegramLink.AWAITING_CONTACT
        and link.expires_at > now and link.contact_attempts_remaining > 0
        and link.chat_id and link.chat.telegram_user_id == sender_id and link.chat.chat_id == chat_id
    )


def _contact_failure(link_id, sender_id, chat_id):
    now = timezone.now()
    with transaction.atomic():
        link = CustomerTelegramLink.objects.select_for_update(of=('self',)).select_related('chat').filter(
            pk=link_id,
        ).first()
        if not _valid_open_link(link, sender_id, chat_id, now):
            if link and link.expires_at <= now:
                link.state = CustomerTelegramLink.EXPIRED
                link.save(update_fields=('state', 'updated_at'))
            return OtpOutcome('invalid')
        return _consume_contact_attempt(link)


def _consume_contact_attempt(link):
    link.contact_attempts_remaining = max(0, link.contact_attempts_remaining - 1)
    if link.contact_attempts_remaining == 0:
        link.state = CustomerTelegramLink.LOCKED
    link.save(update_fields=('contact_attempts_remaining', 'state', 'updated_at'))
    return OtpOutcome('mismatch', link.language)


def _canonical_phone(value):
    formatted = format_phone_number(value)
    return formatted if len(formatted) == 13 and formatted.startswith('+998') and formatted[1:].isdigit() else None
