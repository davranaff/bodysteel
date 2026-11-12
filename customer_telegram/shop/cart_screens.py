"""Cart and delivery-choice screens of the storefront widget."""
from django.core.exceptions import ObjectDoesNotExist

from customer_telegram.i18n import message
from customer_telegram.shop.cart import cart_count, cart_items, order_lines
from customer_telegram.shop.labels import text
from nutrition.checkout import CheckoutUnavailable, build_quote
from store.models import Product
from telegram_widgets.state import clip, fit_rows


DELIVERY_TYPES = ('pickup', 'dcb', 'dtu')
# A widget never scrolls and is at most 600 px tall.
MAXIMUM_ROWS = 7


def cart_screen(chat, notice=''):
    language = chat.language or 'ru'
    items = cart_items(chat)
    products = Product.objects.visible_on_storefront().in_bulk(list(items))
    rows, total = [], 0
    for product_id, quantity in items.items():
        product = products.get(product_id)
        if product is None:
            continue
        line = (int(product.price) - int(product.discounted_price)) * quantity
        total += line
        name = (product.name_uz if language == 'uz' else product.name_ru) or product.name_ru
        rows.append([product.pk, name, quantity, line])
    state = {'v': 'k', 'n': cart_count(chat), 's': total}
    if notice:
        state['m'] = notice
    hidden = fit_rows(state, 'i', rows[:MAXIMUM_ROWS], budgets=(64, 44, 30, 20)) + max(0, len(rows) - MAXIMUM_ROWS)
    if hidden:
        state['mr'] = hidden
    return state


def delivery_screen(chat, notice=''):
    """The ways to get the order, each priced by the same quote the storefront uses."""
    language = chat.language or 'ru'
    lines = order_lines(chat)
    if not lines:
        return cart_screen(chat, notice)
    options, reasons = [], []
    for order_type in DELIVERY_TYPES:
        try:
            quote = build_quote({'baskets': lines, 'type': order_type})
        except CheckoutUnavailable as error:
            reasons.append(error.code)
            continue
        except ObjectDoesNotExist:
            # A delivery type without its tariff configured is not offered.
            continue
        options.append([order_type, delivery_label(language, order_type), quote.delivery_fee, 0])
    state = {'v': 'o', 'n': cart_count(chat), 'dl': options}
    if not options:
        reason = unavailable_reason(language, reasons[0] if reasons else 'other')
        state['m'] = text(language, 'checkout_failed').format(reason)
    elif notice:
        state['m'] = clip(notice, 300)
    return state


def unavailable_reason(language, code):
    key = 'unavailable_{}'.format(code)
    try:
        return text(language, key)
    except KeyError:
        return text(language, 'unavailable_other')


def delivery_label(language, order_type):
    return message(language, 'delivery_{}'.format(order_type))
