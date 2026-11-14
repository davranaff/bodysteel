"""Chat messages that belong to the shop: menu buttons, checkout steps, search."""
from customer_telegram.i18n import message
from customer_telegram.keyboards import main_menu, store_keyboard
from customer_telegram.models import CustomerTelegramLink
from customer_telegram.shop import checkout
from customer_telegram.shop.cart_screens import cart_screen
from customer_telegram.shop.catalog import home_screen, search_screen
from customer_telegram.shop.sender import REFUSED, send_storefront
from customer_telegram.shop.site_link import use_site
from telegram_widgets.rollout import widgets_enabled


MINIMUM_SEARCH = 2
MAXIMUM_SEARCH = 100


def shop_message(chat, payload, message_text, api):
    """Handle a message for the shop, or return ``None`` to let the bot menu handle it."""
    if not widgets_enabled(chat.chat_id):
        return _previous_store_button(chat, message_text, api)
    waiting_link = isinstance(payload.get('contact'), dict) and CustomerTelegramLink.objects.filter(
        chat=chat, state=CustomerTelegramLink.AWAITING_CONTACT,
    ).exists()
    if not waiting_link:
        outcome = checkout.handle_message(chat, payload, api)
        if outcome is not None:
            return outcome
    language = chat.language or 'ru'
    if message_text in {message(language, 'menu_catalog'), message(language, 'menu_store')}:
        return open_catalog(chat, api)
    if message_text == message(language, 'menu_cart'):
        sent = send_storefront(chat, api, cart_screen(chat), screen='k', reply_markup=main_menu(language, chat.chat_id))
        return use_site(chat, api) if sent is REFUSED else 'cart'
    return None


def search_message(chat, message_text, api):
    if not widgets_enabled(chat.chat_id):
        return None
    query = ' '.join(message_text.split())[:MAXIMUM_SEARCH]
    if len(query) < MINIMUM_SEARCH or query.startswith('/'):
        return None
    state = search_screen(chat, query, 0)
    if send_storefront(chat, api, state, screen='s:0', search_query=query) is REFUSED:
        return use_site(chat, api)
    return 'search'


def open_catalog(chat, api):
    if not widgets_enabled(chat.chat_id):
        return None
    language = chat.language or 'ru'
    if send_storefront(chat, api, home_screen(chat), reply_markup=main_menu(language, chat.chat_id)) is REFUSED:
        return use_site(chat, api)
    return 'catalog'


def _previous_store_button(chat, message_text, api):
    """Without widgets the bot behaves as before: the store button links to the site.

    The catalog and cart buttons of a keyboard sent while widgets were on do the same.
    """
    language = chat.language or 'ru'
    if message_text not in {message(language, key) for key in ('menu_store', 'menu_catalog', 'menu_cart')}:
        return None
    api.send_message(chat.chat_id, message(language, 'open_store'), store_keyboard(language))
    return 'store'
