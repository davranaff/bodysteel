"""Tell the customer in the bot that Multicard confirmed the payment of a bot order.

Widget edits are silent, so the order widget turns "paid" and a short card follows
to give the customer a notification. Delivery is best effort: the payment is final.
"""
import logging

from customer_telegram.bot_api import CustomerTelegramApi
from customer_telegram.configuration import CustomerTelegramConfigurationError, customer_telegram_enabled
from customer_telegram.models import CustomerTelegramWidget
from customer_telegram.shop.labels import text
from customer_telegram.shop.order_screens import PAID, order_caption, order_state
from customer_telegram.shop.sender import send_card, update_state


logger = logging.getLogger(__name__)


def notify_customer_paid(order_id, api=None):
    if not customer_telegram_enabled():
        return 0
    widgets = list(CustomerTelegramWidget.objects.select_related('chat', 'order').filter(
        order_id=order_id, kind=CustomerTelegramWidget.ORDER, chat__is_active=True,
    ))
    if not widgets:
        return 0
    try:
        client = api or CustomerTelegramApi()
    except CustomerTelegramConfigurationError:
        return 0
    notified = set()
    for widget in widgets:
        chat = widget.chat
        language = chat.language or 'ru'
        state = order_state(widget.order, language, PAID, notice=text(language, 'paid'))
        update_state(client, widget, state)
        client.edit_reply_markup(chat.chat_id, widget.message_id, {'inline_keyboard': []})
        client.edit_caption(chat.chat_id, widget.message_id, order_caption(chat, state))
        if chat.pk not in notified:
            notified.add(chat.pk)
            send_card(chat.chat_id, client, {'h': order_caption(chat, state), 't': [text(language, 'paid')]},
                      order_caption(chat, state), language)
    return len(notified)
