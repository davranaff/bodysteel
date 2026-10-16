import logging

from teleg.models import Chat as ChatModel
from teleg.views import bot


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
    for chat in ChatModel.objects.all():
        try:
            bot.send_message(chat.chat_id, text=text)
        except Exception:
            # A Telegram outage must not fail the customer's review submission.
            logger.exception('Telegram review notification failed', extra={'review_id': message.get('id')})
