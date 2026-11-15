"""The answer when Telegram refuses a shop widget: the site, never an unanswered tap."""
from html import escape

from customer_telegram.configuration import require_configuration
from customer_telegram.keyboards import main_menu
from customer_telegram.shop.labels import text


def use_site(chat, api):
    """Point to the site in a plain message.

    A refusal of widgets as such has paused them already, so the menu below is the plain one.
    """
    language = chat.language or 'ru'
    body = text(language, 'use_site').format(escape(require_configuration().store_origin))
    send_text = getattr(api, 'send_text', api.send_message)
    send_text(chat.chat_id, body, main_menu(language, chat.chat_id))
    return 'store'
