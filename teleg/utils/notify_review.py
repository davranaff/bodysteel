import logging

from teleg.cards import review_card_html
from teleg.models import Chat as ChatModel
from teleg.views import bot
from teleg.widget_api import StaffWidgetError, send_widget
from telegram_widgets.html import WidgetTooLarge
from telegram_widgets.rollout import widgets_enabled


logger = logging.getLogger(__name__)


def notify_review(message):
    """Tell staff about a new review awaiting moderation; delivery is best-effort."""
    text = (
        f"Новый отзыв ожидает модерации.\n"
        f"id этой комментарий: {message.get('id')} \n"
        f"Никнейм: #{message.get('username')} \n"
        f"Полное Имя: {message.get('first_name')} {message.get('last_name')} \n"
        f"Телефон номер: {message.get('phone')} \n"
        f"Комментарие: {message.get('comment')} \n"
        f"Продукт: {message.get('product')} \n"
        f"Опубликуйте или отклоните его в админке: Магазин → Отзывы."
    )
    try:
        html = review_card_html(message)
    except WidgetTooLarge:
        html = None
    for chat in ChatModel.objects.all():
        if html and widgets_enabled(chat.chat_id) and _send_card(chat.chat_id, html, message):
            continue
        try:
            bot.send_message(chat.chat_id, text=text)
        except Exception:
            # A Telegram outage must not fail the customer's review submission.
            logger.exception('Telegram review notification failed', extra={'review_id': message.get('id')})


def _send_card(chat_id, html, message):
    try:
        send_widget(chat_id, html, '💬 Новый отзыв на модерации')
    except StaffWidgetError:
        logger.warning('Staff review widget refused, sending text', extra={'review_id': message.get('id')})
        return False
    return True
