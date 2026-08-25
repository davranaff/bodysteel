from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from customer_telegram.configuration import require_configuration
from customer_telegram.link_types import START_PARAMETER, StartedLink, TelegramLinkReceipt
from customer_telegram.models import CustomerTelegramChat, CustomerTelegramLink
from customer_telegram.security import PREFIXES, build_deep_link, link_digest, new_start_parameter
from customer_telegram.security import valid_telegram_id
from users.auth.composition import (
    password_reset_telegram_service,
    registration_telegram_start_service,
)
from users.auth.models import AuthChallenge, PhoneVerificationChallenge
from users.auth.errors import AuthProblem
from users.auth.rate_limits import CUSTOMER_TELEGRAM_LINK, consume


def start_registration(values, remote_address, language):
    receipt = registration_telegram_start_service().start_telegram(
        values['email'], values['phone'], remote_address,
        values.get('username', ''), values.get('first_name', ''), values.get('last_name', ''),
    )
    challenge = PhoneVerificationChallenge.objects.get(pk=receipt.challenge_id)
    url = _replace_challenge_link(CustomerTelegramLink.REGISTRATION, challenge, language)
    return TelegramLinkReceipt(str(receipt.challenge_id), receipt.expires_in, receipt.resend_after, url)


def start_password_reset(identifier, remote_address, language):
    receipt = password_reset_telegram_service().start_telegram(identifier, remote_address)
    challenge = AuthChallenge.objects.get(pk=receipt.challenge_id)
    url = _replace_challenge_link(CustomerTelegramLink.PASSWORD_RESET, challenge, language)
    return TelegramLinkReceipt(str(receipt.challenge_id), receipt.expires_in, receipt.resend_after, url)


def start_account_link(user, language):
    configuration = require_configuration()
    now = timezone.now()
    token = new_start_parameter(CustomerTelegramLink.ACCOUNT_LINK)
    with transaction.atomic():
        CustomerTelegramLink.objects.select_for_update().filter(
            purpose=CustomerTelegramLink.ACCOUNT_LINK,
            user=user,
            state__in=(CustomerTelegramLink.AWAITING_START, CustomerTelegramLink.AWAITING_CONTACT),
        ).update(state=CustomerTelegramLink.EXPIRED)
        CustomerTelegramLink.objects.create(
            token_digest=link_digest(token),
            purpose=CustomerTelegramLink.ACCOUNT_LINK,
            user=user,
            language=language,
            contact_attempts_remaining=configuration.contact_max_attempts,
            expires_at=now + timedelta(seconds=configuration.link_ttl_seconds),
        )
    return TelegramLinkReceipt(None, configuration.link_ttl_seconds, None, build_deep_link(token))


def open_link(start_parameter, telegram_user_id, chat_id):
    if not isinstance(start_parameter, str) or not START_PARAMETER.fullmatch(start_parameter):
        return StartedLink(None)
    now = timezone.now()
    try:
        consume(CUSTOMER_TELEGRAM_LINK, start_parameter, now)
    except AuthProblem:
        return StartedLink(None)
    with transaction.atomic():
        link = CustomerTelegramLink.objects.select_for_update().filter(
            token_digest=link_digest(start_parameter),
        ).select_related('registration_challenge', 'auth_challenge__user', 'user').first()
        if not link or link.state not in {
            CustomerTelegramLink.AWAITING_START, CustomerTelegramLink.AWAITING_CONTACT,
        }:
            return StartedLink(None)
        if start_parameter[0] != PREFIXES.get(link.purpose):
            return StartedLink(None)
        if link.expires_at <= now:
            link.state = CustomerTelegramLink.EXPIRED
            link.save(update_fields=('state', 'updated_at'))
            return StartedLink(None)
        if not _target_is_active(link):
            link.state = CustomerTelegramLink.EXPIRED
            link.save(update_fields=('state', 'updated_at'))
            return StartedLink(None)
        if link.state == CustomerTelegramLink.AWAITING_CONTACT and (
            link.chat is None
            or link.chat.telegram_user_id != telegram_user_id
            or link.chat.chat_id != chat_id
        ):
            return StartedLink(None)
        chat = _get_or_create_chat(telegram_user_id, chat_id, link.language, now)
        if chat is None:
            return StartedLink(None)
        CustomerTelegramLink.objects.filter(
            chat=chat,
            state=CustomerTelegramLink.AWAITING_CONTACT,
        ).exclude(pk=link.pk).update(state=CustomerTelegramLink.EXPIRED)
        link.chat = chat
        link.state = CustomerTelegramLink.AWAITING_CONTACT
        link.save(update_fields=('chat', 'state', 'updated_at'))
        linked_reset = (
            link.purpose == CustomerTelegramLink.PASSWORD_RESET
            and link.auth_challenge.user_id is not None
            and chat.user_id == link.auth_challenge.user_id
            and link.auth_challenge.user.is_active
            and link.auth_challenge.user.deleted_at is None
        )
        return StartedLink(link, requires_contact=not linked_reset)


def get_or_create_chat(telegram_user_id, chat_id, language=''):
    return _get_or_create_chat(telegram_user_id, chat_id, language, timezone.now())


def bind_chat_to_user(chat, user, now=None):
    current = now or timezone.now()
    with transaction.atomic():
        locked_chat = CustomerTelegramChat.objects.select_for_update().get(pk=chat.pk)
        old_chat = CustomerTelegramChat.objects.select_for_update().filter(user=user).exclude(
            pk=locked_chat.pk,
        ).first()
        if old_chat:
            old_chat.user = None
            old_chat.linked_at = None
            old_chat.marketing_opt_in = False
            old_chat.marketing_opted_out_at = current
            old_chat.save(update_fields=(
                'user', 'linked_at', 'marketing_opt_in', 'marketing_opted_out_at', 'updated_at',
            ))
        ownership_changed = locked_chat.user_id not in (None, user.pk)
        if ownership_changed:
            locked_chat.marketing_opt_in = False
            locked_chat.marketing_consent_source = ''
            locked_chat.marketing_opted_out_at = current
        locked_chat.user = user
        locked_chat.linked_at = current
        locked_chat.is_active = True
        locked_chat.blocked_at = None
        fields = ['user', 'linked_at', 'is_active', 'blocked_at', 'updated_at']
        if ownership_changed:
            fields.extend(('marketing_opt_in', 'marketing_consent_source', 'marketing_opted_out_at'))
        locked_chat.save(update_fields=fields)
        return locked_chat


def attach_registration_chat(challenge, user, now):
    link = CustomerTelegramLink.objects.select_for_update().filter(
        registration_challenge=challenge,
        state=CustomerTelegramLink.DELIVERED,
        chat__isnull=False,
    ).select_related('chat').first()
    if not link:
        return
    bind_chat_to_user(link.chat, user, now)
    link.state = CustomerTelegramLink.CONSUMED
    link.consumed_at = now
    link.save(update_fields=('state', 'consumed_at', 'updated_at'))


def expire_registration_link(challenge):
    CustomerTelegramLink.objects.filter(
        registration_challenge=challenge,
        state__in=(CustomerTelegramLink.AWAITING_START, CustomerTelegramLink.AWAITING_CONTACT),
    ).update(state=CustomerTelegramLink.EXPIRED)


def unlink_user(user):
    now = timezone.now()
    with transaction.atomic():
        chat = CustomerTelegramChat.objects.select_for_update().filter(user=user).first()
        if chat:
            _unlink_chat(chat, now)
        CustomerTelegramLink.objects.filter(
            user=user,
            state__in=(CustomerTelegramLink.AWAITING_START, CustomerTelegramLink.AWAITING_CONTACT),
        ).update(state=CustomerTelegramLink.EXPIRED)
    return bool(chat)


def unlink_chat(chat):
    with transaction.atomic():
        locked = CustomerTelegramChat.objects.select_for_update().get(pk=chat.pk)
        _unlink_chat(locked, timezone.now())


def _replace_challenge_link(purpose, challenge, language):
    configuration = require_configuration()
    token = new_start_parameter(purpose)
    target = {'registration_challenge': challenge} if purpose == CustomerTelegramLink.REGISTRATION else {
        'auth_challenge': challenge,
    }
    CustomerTelegramLink.objects.update_or_create(
        **target,
        defaults={
            'token_digest': link_digest(token), 'purpose': purpose, 'chat': None,
            'language': language, 'state': CustomerTelegramLink.AWAITING_START,
            'contact_attempts_remaining': configuration.contact_max_attempts,
            'expires_at': challenge.expires_at, 'consumed_at': None,
        },
    )
    return build_deep_link(token)


def _get_or_create_chat(telegram_user_id, chat_id, language, now):
    if not valid_telegram_id(telegram_user_id) or not valid_telegram_id(chat_id) or telegram_user_id != chat_id:
        return None
    try:
        with transaction.atomic():
            chat, created = CustomerTelegramChat.objects.select_for_update().get_or_create(
                telegram_user_id=telegram_user_id,
                defaults={'chat_id': chat_id, 'language': language},
            )
            if not created and chat.chat_id != chat_id:
                return None
            if language and not chat.language:
                chat.language = language
            chat.is_active = True
            chat.blocked_at = None
            chat.last_seen_at = now
            chat.save(update_fields=(
                'language', 'is_active', 'blocked_at', 'last_seen_at', 'updated_at',
            ))
            return chat
    except IntegrityError:
        return None


def _target_is_active(link):
    if link.purpose == CustomerTelegramLink.REGISTRATION:
        challenge = link.registration_challenge
        return (
            challenge.status == PhoneVerificationChallenge.Status.AWAITING
            and challenge.delivery_channel == PhoneVerificationChallenge.DeliveryChannel.TELEGRAM
        )
    if link.purpose == CustomerTelegramLink.PASSWORD_RESET:
        challenge = link.auth_challenge
        return (
            challenge.status == AuthChallenge.Status.AWAITING
            and challenge.channel == AuthChallenge.Channel.TELEGRAM
        )
    return bool(link.user and link.user.is_active and link.user.deleted_at is None)


def _unlink_chat(chat, now):
    chat.user = None
    chat.linked_at = None
    chat.marketing_opt_in = False
    chat.marketing_opted_out_at = now
    chat.save(update_fields=(
        'user', 'linked_at', 'marketing_opt_in', 'marketing_opted_out_at', 'updated_at',
    ))
