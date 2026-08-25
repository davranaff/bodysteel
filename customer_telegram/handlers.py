import re

from django.db import transaction
from django.utils import timezone

from customer_telegram.bot_api import CustomerTelegramApi
from customer_telegram.i18n import message
from customer_telegram.keyboards import (
    contact_keyboard,
    language_keyboard,
    main_menu,
    notification_keyboard,
    remove_keyboard,
    store_keyboard,
    unlink_keyboard,
)
from customer_telegram.links import get_or_create_chat, open_link, unlink_chat
from customer_telegram.models import CustomerTelegramChat, CustomerTelegramLink
from customer_telegram.orders import order_detail, orders_page
from customer_telegram.otp import deliver_linked_reset, process_contact
from customer_telegram.security import valid_telegram_id


COMMAND = re.compile(r'^/([a-z]+)(?:@[A-Za-z0-9_]+)?(?:\s+(.+))?$')
CALLBACK = re.compile(r'^(lang:(?:ru|uz)|notify:(?:on|off)|unlink:(?:yes|no)|orders:\d{1,5}|order:\d{1,12})$')


def handle_update(update, api=None):
    client = api or CustomerTelegramApi()
    if 'message' in update:
        return _handle_message(update['message'], client)
    if 'callback_query' in update:
        return _handle_callback(update['callback_query'], client)
    return 'ignored'


def _handle_message(payload, api):
    identity = _private_identity(payload)
    if identity is None:
        return 'ignored'
    sender_id, chat_id = identity
    text = payload.get('text') if isinstance(payload.get('text'), str) else ''
    command_match = COMMAND.fullmatch(text.strip()) if text else None
    if command_match and command_match.group(1) == 'start':
        return _start(sender_id, chat_id, command_match.group(2), payload, api)
    chat = get_or_create_chat(sender_id, chat_id)
    if chat is None:
        return 'ignored'
    language = chat.language or 'ru'
    if isinstance(payload.get('contact'), dict):
        return _contact(chat, payload['contact'], api)
    if command_match:
        return _command(chat, command_match.group(1), api)
    menu_keys = {key: message(language, key) for key in (
        'menu_orders', 'menu_notifications', 'menu_language', 'menu_store', 'menu_help', 'menu_unlink',
    )}
    if text == menu_keys['menu_orders']:
        return _send_orders(chat, 0, api)
    if text == menu_keys['menu_notifications']:
        return _notifications(chat, api)
    if text == menu_keys['menu_language']:
        api.send_message(chat.chat_id, message(language, 'choose_language'), language_keyboard())
        return 'language'
    if text == menu_keys['menu_store']:
        api.send_message(chat.chat_id, message(language, 'open_store'), store_keyboard(language))
        return 'store'
    if text == menu_keys['menu_help']:
        return _command(chat, 'help', api)
    if text == menu_keys['menu_unlink']:
        return _command(chat, 'unlink', api)
    api.send_message(chat.chat_id, message(language, 'unknown'), main_menu(language))
    return 'unknown'


def _start(sender_id, chat_id, start_parameter, payload, api):
    if start_parameter:
        started = open_link(start_parameter.strip(), sender_id, chat_id)
        if not started.link:
            api.send_message(chat_id, message('ru', 'invalid_link'))
            return 'invalid_link'
        language = started.link.language
        if not started.requires_contact:
            outcome = deliver_linked_reset(started.link.pk, sender_id, chat_id, api)
            return _otp_outcome(started.link.chat, outcome, api)
        api.send_message(
            chat_id, message(language, 'request_contact'), contact_keyboard(language),
        )
        return 'contact_requested'
    chat = get_or_create_chat(sender_id, chat_id)
    if chat is None:
        return 'ignored'
    if not chat.language:
        api.send_message(chat_id, message('ru', 'choose_language'), language_keyboard())
        return 'language'
    api.send_message(
        chat_id,
        '{}\n{}'.format(message(chat.language, 'welcome'), message(chat.language, 'help')),
        main_menu(chat.language),
    )
    return 'started'


def _contact(chat, contact, api):
    link = CustomerTelegramLink.objects.filter(
        chat=chat, state=CustomerTelegramLink.AWAITING_CONTACT,
    ).order_by('-created_at').first()
    if not link:
        api.send_message(chat.chat_id, message(chat.language or 'ru', 'invalid_link'), remove_keyboard())
        return 'invalid_link'
    outcome = process_contact(link.pk, chat.telegram_user_id, chat.chat_id, contact, api)
    return _otp_outcome(chat, outcome, api)


def _otp_outcome(chat, outcome, api):
    language = outcome.language or chat.language or 'ru'
    keys = {
        'linked': 'linked', 'delivered': 'otp_delivered', 'failed': 'otp_failed',
        'mismatch': 'contact_mismatch', 'invalid': 'invalid_link',
    }
    api.send_message(chat.chat_id, message(language, keys.get(outcome.status, 'generic_error')), remove_keyboard())
    if outcome.status in {'linked', 'delivered'}:
        api.send_message(chat.chat_id, message(language, 'notifications_prompt'), notification_keyboard(language))
    return outcome.status


def _command(chat, command, api):
    language = chat.language or 'ru'
    if command == 'orders':
        return _send_orders(chat, 0, api)
    if command == 'language':
        api.send_message(chat.chat_id, message(language, 'choose_language'), language_keyboard())
        return 'language'
    if command == 'notifications':
        return _notifications(chat, api)
    if command == 'stop':
        _set_notifications(chat, False, 'command')
        api.send_message(chat.chat_id, message(language, 'notifications_off'), main_menu(language))
        return 'notifications_off'
    if command == 'unlink':
        api.send_message(chat.chat_id, message(language, 'unlink_confirm'), unlink_keyboard(language))
        return 'unlink_confirm'
    if command == 'help':
        api.send_message(chat.chat_id, message(language, 'help'), main_menu(language))
        return 'help'
    api.send_message(chat.chat_id, message(language, 'unknown'), main_menu(language))
    return 'unknown'


def _handle_callback(payload, api):
    callback_id = payload.get('id')
    data = payload.get('data')
    message_payload = payload.get('message')
    sender_id = payload.get('from', {}).get('id')
    identity = _private_identity({
        'from': payload.get('from'),
        'chat': message_payload.get('chat') if isinstance(message_payload, dict) else None,
    })
    if not isinstance(callback_id, str) or not isinstance(data, str) or not CALLBACK.fullmatch(data):
        return 'ignored'
    if identity is None or identity[0] != sender_id:
        api.answer_callback_query(callback_id)
        return 'denied'
    chat = CustomerTelegramChat.objects.filter(telegram_user_id=sender_id, chat_id=identity[1]).first()
    if not chat:
        api.answer_callback_query(callback_id)
        return 'denied'
    api.answer_callback_query(callback_id)
    language = chat.language or 'ru'
    if data.startswith('lang:'):
        chat.language = data[-2:]
        chat.save(update_fields=('language', 'updated_at'))
        api.send_message(chat.chat_id, message(chat.language, 'welcome'), main_menu(chat.language))
        return 'language'
    if data.startswith('notify:'):
        enabled = data.endswith('on')
        _set_notifications(chat, enabled, 'bot_callback')
        api.send_message(chat.chat_id, message(language, 'notifications_on' if enabled else 'notifications_off'))
        return 'notifications'
    if data == 'unlink:yes':
        unlink_chat(chat)
        api.send_message(chat.chat_id, message(language, 'unlinked'), main_menu(language))
        return 'unlinked'
    if data == 'unlink:no':
        return 'cancelled'
    if data.startswith('orders:'):
        return _send_orders(chat, int(data.split(':')[1]), api)
    detail = order_detail(chat, int(data.split(':')[1]))
    api.send_message(chat.chat_id, detail.text, detail.reply_markup)
    return 'order'


def _notifications(chat, api):
    language = chat.language or 'ru'
    current = 'notifications_on' if chat.marketing_opt_in else 'notifications_off'
    api.send_message(
        chat.chat_id,
        '{}\n\n{}'.format(message(language, current), message(language, 'notifications_prompt')),
        notification_keyboard(language),
    )
    return 'notifications'


def _set_notifications(chat, enabled, source):
    now = timezone.now()
    with transaction.atomic():
        locked = CustomerTelegramChat.objects.select_for_update().get(pk=chat.pk)
        locked.marketing_opt_in = enabled
        locked.marketing_consent_source = source if enabled else ''
        locked.marketing_opted_in_at = now if enabled else locked.marketing_opted_in_at
        locked.marketing_opted_out_at = None if enabled else now
        locked.save(update_fields=(
            'marketing_opt_in', 'marketing_consent_source', 'marketing_opted_in_at',
            'marketing_opted_out_at', 'updated_at',
        ))


def _send_orders(chat, page, api):
    value = orders_page(chat, page)
    api.send_message(chat.chat_id, value.text, value.reply_markup)
    return 'orders'


def _private_identity(payload):
    if not isinstance(payload, dict):
        return None
    sender = payload.get('from')
    chat = payload.get('chat')
    if not isinstance(sender, dict) or not isinstance(chat, dict) or chat.get('type') != 'private':
        return None
    sender_id, chat_id = sender.get('id'), chat.get('id')
    if sender.get('is_bot') is True or not valid_telegram_id(sender_id) or not valid_telegram_id(chat_id):
        return None
    return sender_id, chat_id
