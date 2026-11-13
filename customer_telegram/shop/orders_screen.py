"""The customer's recent orders as a storefront screen: number, status and total."""
from customer_telegram.i18n import message
from customer_telegram.orders import visible_orders
from customer_telegram.shop.cart import cart_count
from customer_telegram.shop.labels import text
from telegram_widgets.state import fit_rows


MAXIMUM_ORDERS = 6


def orders_screen(chat):
    language = chat.language or 'ru'
    orders = list(visible_orders(chat).only(
        'id', 'order_code', 'total_price', 'payment_status', 'fulfillment_status',
    ).order_by('-created_at')[:MAXIMUM_ORDERS])
    state = {'v': 'r', 'n': cart_count(chat)}
    if not orders:
        state['m'] = text(language, 'no_orders')
        return state
    rows = [[str(order.order_code), _status(language, order), int(order.total_price), _tone(order)] for order in orders]
    fit_rows(state, 'i', rows, budgets=(60, 40, 24))
    return state


def _status(language, order):
    if order.fulfillment_status == 'cancelled':
        return message(language, 'fulfillment_cancelled')
    return '{} · {}'.format(
        message(language, 'payment_{}'.format(order.payment_status)),
        message(language, 'fulfillment_{}'.format(order.fulfillment_status)),
    )


def _tone(order):
    if order.fulfillment_status == 'cancelled' or order.payment_status == 'failed':
        return 'x'
    return 'ok' if order.payment_status == 'paid' else ''
