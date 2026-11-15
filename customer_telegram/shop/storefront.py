"""Requests from the storefront widget: browse, search, product, cart, delivery choice."""
import re

from customer_telegram.shop.cart import cart_count, change_quantity
from customer_telegram.shop.cart_screens import DELIVERY_TYPES, cart_screen, delivery_screen
from customer_telegram.shop.catalog import category_screen, home_screen, product_screen, search_screen
from customer_telegram.shop.checkout import begin
from customer_telegram.shop.labels import text
from customer_telegram.shop.orders_screen import orders_screen
from customer_telegram.shop.product_card import visible_product
from customer_telegram.shop.sender import send_product


REQUEST = re.compile(r'^(?:h|k|o|r|c:\d{1,9}:\d{1,4}|s:\d{1,4}|[pad]:\d{1,9}|t:(?:pickup|dcb|dtu))$')


def storefront_request(chat, widget, data, api):
    """Returns the new screen; ``data`` was checked against ``REQUEST``."""
    kind, _, rest = data.partition(':')
    if kind in {'a', 'd'}:
        notice = change_quantity(chat, int(rest), 1 if kind == 'a' else -1)
        return render(chat, widget, widget.screen, text(chat.language, notice) if notice else '')
    if kind == 't':
        return _choose_delivery(chat, rest, api)
    if kind == 'p':
        return _open_product(chat, widget, int(rest), api)
    return render(chat, widget, data)


def render(chat, widget, screen, notice=''):
    kind, _, rest = (screen or 'h').partition(':')
    if kind == 'c':
        category_id, _, page = rest.partition(':')
        state = category_screen(chat, int(category_id), int(page or 0))
    elif kind == 's':
        state = search_screen(chat, widget.search_query, int(rest or 0))
    elif kind == 'p':
        state = product_screen(chat, int(rest), back=widget.last_list or 'h')
    elif kind == 'k':
        state = cart_screen(chat)
    elif kind == 'o':
        state = delivery_screen(chat)
    elif kind == 'r':
        state = orders_screen(chat)
    else:
        screen, state = 'h', home_screen(chat)
    if notice:
        state['m'] = notice
    widget.screen = screen
    if kind in {'c', 's', 'h'}:
        widget.last_list = screen
    widget.save(update_fields=('screen', 'last_list'))
    return state


def _open_product(chat, widget, product_id, api):
    """Send the product card with its photo below; the storefront stays where it was."""
    product = visible_product(product_id)
    if product is None:
        return render(chat, widget, widget.screen, text(chat.language, 'gone'))
    if not send_product(chat, api, product):
        # Telegram refused the card: fall back to the compact screen inside the storefront.
        return render(chat, widget, 'p:{}'.format(product_id))
    return render(chat, widget, widget.screen, text(chat.language, 'card_below'))


def _choose_delivery(chat, delivery_type, api):
    if delivery_type not in DELIVERY_TYPES:
        return delivery_screen(chat)
    begin(chat, delivery_type, api)
    return {'v': 'w', 'n': cart_count(chat), 'tx': text(chat.language, 'ask_contact')}
