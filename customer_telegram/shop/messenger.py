"""Every bot reply as a widget card: the handlers keep calling ``send_message``.

Inline buttons become card buttons whose taps arrive as widget queries with the same
``callback_data``. Reply keyboards stay native under the widget. If Telegram refuses
the widget, the reply goes out as the original text so the customer is never left
without an answer. One-time codes use ``send_text`` and stay plain messages, so the
code is visible in the notification.
"""
import re
from html import unescape

from customer_telegram.bot_api import DeliveryStatus
from customer_telegram.models import CustomerTelegramChat, CustomerTelegramWidget
from customer_telegram.shop.sender import send_card
from telegram_widgets.html import WidgetTooLarge
from telegram_widgets.state import clip


TAG = re.compile(r'<[^>]+>')
BOLD_LINE = re.compile(r'^\s*(?:\S+\s+)?<b>[^<]*</b>\s*$')


class WidgetMessenger:
    def __init__(self, api):
        self._api = api

    def __getattr__(self, name):
        return getattr(self._api, name)

    def send_text(self, chat_id, text, reply_markup=None, parse_mode='HTML'):
        return self._api.send_message(chat_id, text, reply_markup, parse_mode)

    def send_message(self, chat_id, text, reply_markup=None, parse_mode='HTML'):
        chat = CustomerTelegramChat.objects.filter(chat_id=chat_id).first()
        language = (chat.language if chat else '') or 'ru'
        state, native_markup = card_from_message(text, reply_markup)
        caption = state.get('h') or (state['t'][0].lstrip('!~=') if state.get('t') else '')
        try:
            result = send_card(chat_id, self._api, state, clip(caption, 200), language, native_markup)
        except WidgetTooLarge:
            result = None
        if result is not None and result.status is DeliveryStatus.SENT and chat and state.get('b'):
            CustomerTelegramWidget.objects.get_or_create(
                chat=chat, message_id=result.message_id, defaults={'kind': CustomerTelegramWidget.CARD},
            )
        # Only a refused widget falls back: an unknown outcome may already be delivered.
        if result is not None and result.status is not DeliveryStatus.FAILED:
            return result
        return self._api.send_message(chat_id, text, reply_markup, parse_mode)


def card_from_message(text, reply_markup=None):
    lines = [line for line in str(text or '').split('\n')]
    state = {}
    if len(lines) > 1 and BOLD_LINE.match(lines[0]):
        state['h'] = _plain(lines.pop(0))
    body = []
    for line in lines:
        plain = _plain(line)
        if not plain:
            if body and body[-1] != '-':
                body.append('-')
            continue
        body.append(('!' if BOLD_LINE.match(line) else '') + plain)
    while body and body[-1] == '-':
        body.pop()
    state['t'] = body
    native = None
    if isinstance(reply_markup, dict) and 'inline_keyboard' in reply_markup:
        for row in reply_markup['inline_keyboard']:
            for button in row:
                if 'callback_data' in button:
                    state.setdefault('b', []).append([button['text'], button['callback_data']])
                elif 'url' in button:
                    state.setdefault('u', []).append([button['text'], button['url']])
    elif reply_markup:
        native = reply_markup
    return state, native


def _plain(line):
    return ' '.join(unescape(TAG.sub('', line)).split())
