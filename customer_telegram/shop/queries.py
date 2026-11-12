"""Answer ``widget_query`` updates: every query gets an answer within Telegram's 15 seconds.

The query carries no widget state, so it is checked against the widget the bot sent:
the sender must own the private chat and the message must be one of the bot's widgets.
The new screen goes back in the answer at once and is then saved as the chat state.
"""
import logging

from customer_telegram.models import CustomerTelegramChat, CustomerTelegramWidget
from customer_telegram.security import valid_telegram_id
from customer_telegram.shop.labels import widget_labels
from customer_telegram.shop.order_screens import PAID, order_caption
from customer_telegram.shop.placement import payment_state, place_and_pay
from customer_telegram.shop.sender import send_storefront, update_state
from customer_telegram.shop.storefront import REQUEST, render, storefront_request
from telegram_widgets.state import encode, fits, valid_request


logger = logging.getLogger(__name__)
ORDER_REQUESTS = {'y', 'v', 'z', 'O'}


def handle_widget_query(payload, api, callback_handler):
    query_id = payload.get('id') if isinstance(payload, dict) else None
    if not isinstance(query_id, str) or not query_id:
        return 'ignored'
    try:
        return _handle(payload, api, callback_handler)
    except Exception:
        logger.exception('Customer widget query failed')
        api.answer_widget_query(query_id, None)
        return 'failed'


def _handle(payload, api, callback_handler):
    query_id, data = payload['id'], payload.get('data')
    widget = _owned_widget(payload)
    if widget is None or not valid_request(data):
        api.answer_widget_query(query_id, None)
        return 'denied'
    chat = widget.chat
    if widget.kind == CustomerTelegramWidget.STOREFRONT and REQUEST.fullmatch(data):
        return _answer(api, query_id, widget, storefront_request(chat, widget, data, api))
    if widget.kind == CustomerTelegramWidget.ORDER and data in ORDER_REQUESTS:
        return _order_request(chat, widget, data, api, query_id, callback_handler)
    if widget.kind == CustomerTelegramWidget.CARD:
        api.answer_widget_query(query_id, None)
        return callback_handler(chat, data)
    api.answer_widget_query(query_id, None)
    return 'denied'


def _order_request(chat, widget, data, api, query_id, callback_handler):
    if data == 'O':
        api.answer_widget_query(query_id, None)
        return callback_handler(chat, 'orders:0')
    if data == 'z':
        api.answer_widget_query(query_id, None)
        state = render(chat, widget, 'k')
        send_storefront(chat, api, state, screen='k')
        return 'cart'
    if data == 'v':
        return _answer(api, query_id, widget, payment_state(chat, widget))
    state, pay_url = place_and_pay(chat, widget)
    result = _answer(api, query_id, widget, state)
    if pay_url:
        # A native button under the widget opens the payment page without the
        # widget's link confirmation, and keeps working in apps without widgets.
        label = '💳 {}'.format(widget_labels(chat.language)['pay'])
        api.edit_reply_markup(chat.chat_id, widget.message_id, {'inline_keyboard': [[{'text': label, 'url': pay_url}]]})
    if state.get('st') == PAID:
        api.edit_caption(chat.chat_id, widget.message_id, order_caption(chat, state))
    return result


def _answer(api, query_id, widget, state):
    if not fits(state):
        logger.error('Customer widget state exceeds 1024 bytes', extra={'view': state.get('v')})
        api.answer_widget_query(query_id, None)
        return 'failed'
    data = encode(state)
    api.answer_widget_query(query_id, data)
    update_state(api, widget, state)
    return 'answered'


def _owned_widget(payload):
    sender, chat = payload.get('from'), payload.get('chat')
    message_id = payload.get('message_id')
    if not isinstance(sender, dict) or not isinstance(chat, dict) or chat.get('type') != 'private':
        return None
    sender_id, chat_id = sender.get('id'), chat.get('id')
    if sender.get('is_bot') is True or not valid_telegram_id(sender_id) or sender_id != chat_id:
        return None
    if not isinstance(message_id, int) or isinstance(message_id, bool) or message_id <= 0:
        return None
    owner = CustomerTelegramChat.objects.filter(telegram_user_id=sender_id, chat_id=chat_id, is_active=True).first()
    if owner is None:
        return None
    return CustomerTelegramWidget.objects.select_related('chat', 'chat__user', 'order').filter(
        chat=owner, message_id=message_id,
    ).first()
