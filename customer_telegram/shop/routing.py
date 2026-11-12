"""Chat messages that belong to the shop: menu buttons, checkout steps, search."""
from customer_telegram.i18n import message
from customer_telegram.keyboards import main_menu
from customer_telegram.models import CustomerTelegramLink
from customer_telegram.shop import checkout
from customer_telegram.shop.cart_screens import cart_screen
from customer_telegram.shop.catalog import home_screen, search_screen
from customer_telegram.shop.sender import send_storefront


MINIMUM_SEARCH = 2
MAXIMUM_SEARCH = 100


def shop_message(chat, payload, message_text, api):
    """Handle a message for the shop, or return ``None`` to let the bot menu handle it."""
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
        send_storefront(chat, api, cart_screen(chat), screen='k', reply_markup=main_menu(language))
        return 'cart'
    return None


def search_message(chat, message_text, api):
    query = ' '.join(message_text.split())[:MAXIMUM_SEARCH]
    if len(query) < MINIMUM_SEARCH or query.startswith('/'):
        return None
    state = search_screen(chat, query, 0)
    send_storefront(chat, api, state, screen='s:0', search_query=query)
    return 'search'


def open_catalog(chat, api):
    language = chat.language or 'ru'
    send_storefront(chat, api, home_screen(chat), reply_markup=main_menu(language))
    return 'catalog'
