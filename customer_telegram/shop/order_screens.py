"""States of the order widget: confirmation, waiting for payment, paid."""
from django.core.exceptions import ObjectDoesNotExist

from customer_telegram.i18n import message
from customer_telegram.shop.cart import order_lines
from customer_telegram.shop.cart_screens import MAXIMUM_ROWS, unavailable_reason
from customer_telegram.shop.labels import text
from nutrition.checkout import CheckoutUnavailable, build_quote
from telegram_widgets.state import clip, fit_rows


CONFIRM = 'c'
PENDING = 'p'
PAID = 'ok'
FAILED = 'x'
CASH = 'cod'


def confirm_state(chat, checkout, notice=''):
    language = chat.language or 'ru'
    state = _contact_fields(language, checkout.delivery_type, checkout.full_name, checkout.phone, checkout.address)
    state['st'] = CONFIRM
    lines = order_lines(chat)
    try:
        quote = build_quote({'baskets': lines, 'type': checkout.delivery_type}) if lines else None
    except CheckoutUnavailable as error:
        quote = None
        notice = notice or _reason(language, error.code)
    except ObjectDoesNotExist:
        quote = None
    if quote is None:
        state.update(st=FAILED, s=0, f=0, t=0)
        state['m'] = notice or text(language, 'unavailable_other')
        return state
    rows = []
    for product_id, quantity in quote.quantities.items():
        product = quote.products[product_id]
        name = (product.name_uz if language == 'uz' else product.name_ru) or product.name_ru
        rows.append([name, quantity, (int(product.price) - int(product.discounted_price)) * quantity])
    state.update(s=quote.subtotal, f=quote.delivery_fee, t=quote.subtotal + quote.delivery_fee)
    if notice:
        state['m'] = clip(notice, 200)
    _fit_items(state, rows)
    return state


def order_state(order, language, status, url=None, notice=''):
    state = _contact_fields(language, order.type, order.full_name, order.phone, order.address)
    state.update(st=status, c=order.order_code, s=int(order.subtotal_price or 0),
                 f=int(order.delivery_fee or 0), t=int(order.total_price))
    if url and len(url) <= 256:
        state['u'] = url
    if notice:
        state['m'] = clip(notice, 200)
    rows = []
    for basket in order.baskets.all():
        name = (basket.product_name_uz if language == 'uz' else basket.product_name_ru) or basket.product_name_ru
        if not name and basket.product_id:
            name = basket.product.name_uz if language == 'uz' else basket.product.name_ru
        rows.append([name or message(language, 'product'), int(basket.quantity), int(basket.price)])
    _fit_items(state, rows)
    return state


def order_caption(chat, state):
    language = chat.language or 'ru'
    if state.get('st') == PAID:
        return text(language, 'order_caption_paid').format(state.get('c', ''))
    return text(language, 'order_caption').format('{:,}'.format(int(state.get('t') or 0)).replace(',', ' '))


def _contact_fields(language, delivery_type, full_name, phone, address):
    state = {'v': 'o'}
    if delivery_type in {'pickup', 'dcb', 'dtu'}:
        state['y'] = message(language, 'delivery_{}'.format(delivery_type))
    state['nm'] = clip(full_name, 60)
    state['ph'] = phone or ''
    if delivery_type != 'pickup' and address:
        state['ad'] = clip(address, 120)
    return state


def _fit_items(state, rows):
    hidden = fit_rows(state, 'i', rows[:MAXIMUM_ROWS], title=0, budgets=(64, 44, 30, 20)) + max(0, len(rows) - MAXIMUM_ROWS)
    if hidden:
        state['mr'] = hidden


def _reason(language, code):
    return text(language, 'checkout_failed').format(unavailable_reason(language, code))
