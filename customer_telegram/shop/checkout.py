"""Collect the delivery details in the chat, then show the order for confirmation.

Widgets have no text input, so the phone (contact button), the address (location or
a typed message) arrive as ordinary chat messages while a checkout step waits.
"""
import hmac
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from django.db import transaction

from customer_telegram.bot_api import DeliveryStatus
from customer_telegram.configuration import require_configuration
from customer_telegram.i18n import MESSAGES
from customer_telegram.keyboards import contact_keyboard, remove_keyboard
from customer_telegram.models import CustomerTelegramCheckout
from customer_telegram.shop.labels import text
from customer_telegram.shop.order_screens import confirm_state, order_caption
from customer_telegram.shop.sender import REFUSED, send_card, send_order
from customer_telegram.shop.site_link import use_site
from store.geocoding.bounds import inside_uzbekistan
from store.utils.format_phone import format_phone_number
from telegram_widgets.state import clip


# The staff see this on the order next to the map links built from the coordinates.
LOCATION_ADDRESS = '📍 Геолокация из Telegram'


def begin(chat, delivery_type, api):
    """Start a new checkout attempt for the cart and ask for the first missing detail."""
    with transaction.atomic():
        checkout, _ = CustomerTelegramCheckout.objects.select_for_update().get_or_create(chat=chat)
        checkout.attempt += 1
        checkout.delivery_type = delivery_type
        checkout.order = None
        checkout.step = CustomerTelegramCheckout.CONTACT
        checkout.save()
    _ask_contact(chat, checkout, api)
    return checkout


def handle_message(chat, payload, api):
    """Consume a chat message for a waiting checkout step; ``None`` if none waits."""
    checkout = CustomerTelegramCheckout.objects.filter(chat=chat).first()
    if checkout is None or checkout.step not in {checkout.CONTACT, checkout.ADDRESS}:
        return None
    language = chat.language or 'ru'
    message_text = payload.get('text') if isinstance(payload.get('text'), str) else ''
    # Commands and menu buttons always work; a typed text while the phone is
    # awaited is a search, not a phone number.
    if message_text.startswith('/') or message_text in _menu_labels(language):
        return None
    if message_text == text(language, 'use_saved'):
        return _use_saved(chat, checkout, api)
    if checkout.step == checkout.CONTACT:
        if message_text and not isinstance(payload.get('contact'), dict):
            return None
        return _contact(chat, checkout, payload, api)
    return _address(chat, checkout, payload, message_text, api)


def idempotency_key(checkout):
    digest = hmac.new(
        require_configuration().link_hash_key,
        'checkout:{}:{}'.format(checkout.pk, checkout.attempt).encode('ascii'),
        sha256,
    ).hexdigest()
    return 'tg.{}'.format(digest[:48])


def _contact(chat, checkout, payload, api):
    language = chat.language or 'ru'
    contact = payload.get('contact')
    sender = payload.get('from') or {}
    if not isinstance(contact, dict) or contact.get('user_id') != sender.get('id'):
        _card(chat, api, text(language, 'own_contact'), contact_keyboard(language))
        return 'checkout_contact'
    phone = format_phone_number(str(contact.get('phone_number') or ''))
    if len(phone) != 13 or not phone.startswith('+998') or not phone[1:].isdigit():
        _card(chat, api, text(language, 'bad_phone'), contact_keyboard(language))
        return 'checkout_contact'
    checkout.phone = phone
    checkout.full_name = clip(' '.join(filter(None, (contact.get('first_name'), contact.get('last_name')))), 255)
    return _after_contact(chat, checkout, api)


def _after_contact(chat, checkout, api):
    if checkout.delivery_type == 'pickup':
        checkout.address, checkout.latitude, checkout.longitude = '', None, None
        return _confirm(chat, checkout, api)
    checkout.step = checkout.ADDRESS
    checkout.save()
    language = chat.language or 'ru'
    _card(chat, api, text(language, 'ask_address'), _location_keyboard(language, bool(checkout.address)))
    return 'checkout_address'


def _address(chat, checkout, payload, message_text, api):
    language = chat.language or 'ru'
    location = payload.get('location')
    if isinstance(location, dict):
        latitude, longitude = _coordinate(location.get('latitude')), _coordinate(location.get('longitude'))
        if latitude is None or longitude is None or not inside_uzbekistan(latitude, longitude):
            _card(chat, api, text(language, 'outside'), _location_keyboard(language, False))
            return 'checkout_address'
        checkout.latitude, checkout.longitude = latitude, longitude
        checkout.address = LOCATION_ADDRESS
        return _confirm(chat, checkout, api)
    address = ' '.join(message_text.split())
    if len(address) < 5:
        _card(chat, api, text(language, 'bad_address'), _location_keyboard(language, False))
        return 'checkout_address'
    checkout.address, checkout.latitude, checkout.longitude = clip(address, 255), None, None
    return _confirm(chat, checkout, api)


def _use_saved(chat, checkout, api):
    if checkout.step == checkout.CONTACT and checkout.phone:
        return _after_contact(chat, checkout, api)
    if checkout.step == checkout.ADDRESS and checkout.address:
        return _confirm(chat, checkout, api)
    return None


def _confirm(chat, checkout, api):
    checkout.step = checkout.CONFIRM
    checkout.save()
    state = confirm_state(chat, checkout)
    if send_order(chat, api, state, order_caption(chat, state), reply_markup=remove_keyboard()) is REFUSED:
        # The order is confirmed with a widget button; without it the site takes the order.
        return use_site(chat, api)
    return 'checkout_confirm'


def _ask_contact(chat, checkout, api):
    language = chat.language or 'ru'
    keyboard = contact_keyboard(language)
    if checkout.phone:
        keyboard['keyboard'].append([{'text': text(language, 'use_saved')}])
    _card(chat, api, text(language, 'ask_contact'), keyboard)


def _location_keyboard(language, saved):
    rows = [[{'text': text(language, 'share_location'), 'request_location': True}]]
    if saved:
        rows.append([{'text': text(language, 'use_saved')}])
    return {'keyboard': rows, 'resize_keyboard': True, 'one_time_keyboard': True}


def _menu_labels(language):
    return {value for key, value in MESSAGES['uz' if language == 'uz' else 'ru'].items() if key.startswith('menu_')}


def _card(chat, api, body, keyboard):
    language = chat.language or 'ru'
    result = send_card(chat.chat_id, api, {'t': [body]}, clip(body, 200), language, keyboard)
    if result.status is DeliveryStatus.FAILED:
        # A refused card goes out as a plain message with the same contact or location keyboard.
        send_text = getattr(api, 'send_text', api.send_message)
        send_text(chat.chat_id, body, keyboard)


def _coordinate(value):
    try:
        return Decimal(str(value)).quantize(Decimal('0.000001'))
    except (InvalidOperation, ValueError, TypeError):
        return None
