import logging
from html import escape

from telebot import types

from teleg.cards import admin_link, review_card_html
from teleg.models import Chat as ChatModel
from teleg.views import bot
from teleg.widget_api import StaffWidgetError, send_widget
from telegram_widgets.html import WidgetTooLarge
from telegram_widgets.rollout import widgets_enabled


logger = logging.getLogger(__name__)
COMMENT_LIMIT = 1500


def notify_review(message):
    """Tell staff about a new review awaiting moderation; delivery is best-effort."""
    text = format_review_notification(message)
    buttons = _review_buttons()
    try:
        html = review_card_html(message)
    except WidgetTooLarge:
        html = None
    for chat in ChatModel.objects.all():
        if html and widgets_enabled(chat.chat_id) and _send_card(chat.chat_id, html, message):
            continue
        try:
            bot.send_message(chat.chat_id, text=text, parse_mode='HTML', reply_markup=buttons)
        except Exception:
            # A Telegram outage must not fail the customer's review submission.
            logger.exception('Telegram review notification failed', extra={'review_id': message.get('id')})


def format_review_notification(message):
    name = ' '.join(str(message.get(key) or '').strip() for key in ('first_name', 'last_name')).strip()
    who = ' · '.join(escape(value) for value in (name, str(message.get('phone') or '').strip()) if value)
    comment = ' '.join(str(message.get('comment') or '').split())[:COMMENT_LIMIT] or '—'
    return '\n'.join((
        '💬 <b>Новый отзыв на модерации</b>',
        '<i>Отзыв № {}</i>'.format(escape(str(message.get('id') or '—'))),
        '',
        '📦 <b>{}</b>'.format(escape(str(message.get('product') or 'Товар'))),
        '👤 {}'.format(who or '—'),
        '<blockquote>{}</blockquote>'.format(escape(comment)),
        'Опубликуйте или отклоните его в админке: Магазин → Отзывы.',
    ))


def _review_buttons():
    admin = admin_link('store_review_changelist')
    if not admin:
        return None
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton('Открыть отзывы', url=admin))
    return markup


def _send_card(chat_id, html, message):
    try:
        send_widget(chat_id, html, '💬 Новый отзыв на модерации')
    except StaffWidgetError as error:
        logger.warning('Staff review widget refused (%s), sending text', error.code or 'no code',
                       extra={'review_id': message.get('id')})
        return False
    return True
