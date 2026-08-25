from dataclasses import dataclass
from html import escape

from django.utils import timezone

from customer_telegram.i18n import message
from customer_telegram.keyboards import orders_keyboard
from store.models import Order


PAGE_SIZE = 5


@dataclass(frozen=True)
class OrdersMessage:
    text: str
    reply_markup: dict | None = None


def orders_page(chat, page):
    if not _active_link(chat) or not isinstance(page, int) or not 0 <= page <= 10_000:
        return OrdersMessage(message(chat.language or 'ru', 'not_linked'))
    language = chat.language or 'ru'
    offset = page * PAGE_SIZE
    orders = list(Order.objects.filter(user=chat.user).only(
        'id', 'order_code', 'created_at', 'total_price', 'payment_status', 'fulfillment_status',
    ).order_by('-created_at')[offset:offset + PAGE_SIZE + 1])
    if not orders:
        return OrdersMessage(message(language, 'no_orders'))
    has_next = len(orders) > PAGE_SIZE
    visible = orders[:PAGE_SIZE]
    lines = [message(language, 'orders_title')]
    for order in visible:
        created = timezone.localtime(order.created_at).strftime('%d.%m.%Y')
        lines.extend((
            '',
            '<b>#{} · {}</b>'.format(escape(order.order_code), created),
            '{}: {} UZS'.format(message(language, 'order_total'), _money(order.total_price)),
            '{}: {}'.format(message(language, 'order_payment'), _status(language, 'payment', order.payment_status)),
            '{}: {}'.format(
                message(language, 'order_fulfillment'),
                _status(language, 'fulfillment', order.fulfillment_status),
            ),
        ))
    keyboard = orders_keyboard(
        language, page, page > 0, has_next,
        [(order.pk, order.order_code) for order in visible],
    )
    return OrdersMessage('\n'.join(lines), keyboard)


def order_detail(chat, order_id):
    if not _active_link(chat) or not isinstance(order_id, int) or order_id < 1:
        return OrdersMessage(message(chat.language or 'ru', 'callback_denied'))
    order = Order.objects.filter(pk=order_id, user=chat.user).prefetch_related(
        'baskets__product',
    ).first()
    language = chat.language or 'ru'
    if not order:
        return OrdersMessage(message(language, 'callback_denied'))
    created = timezone.localtime(order.created_at).strftime('%d.%m.%Y · %H:%M')
    lines = [
        '📦 <b>{} #{}</b>'.format(message(language, 'order'), escape(order.order_code)),
        created,
        '{}: {} UZS'.format(message(language, 'order_total'), _money(order.total_price)),
        '{}: {}'.format(message(language, 'order_payment'), _status(language, 'payment', order.payment_status)),
        '{}: {}'.format(
            message(language, 'order_fulfillment'),
            _status(language, 'fulfillment', order.fulfillment_status),
        ),
        '{}: {}'.format(message(language, 'order_delivery'), _delivery(language, order.type)),
        '',
        '<b>{}</b>'.format(message(language, 'order_items')),
    ]
    for index, basket in enumerate(order.baskets.all(), start=1):
        name = _product_name(basket, language)
        quantity = int(basket.quantity)
        line_total = int(basket.price)
        unit_price = int(basket.unit_price) if int(basket.unit_price) > 0 else (
            line_total // quantity if quantity else line_total
        )
        lines.extend((
            '',
            '{}. <b>{}</b>'.format(index, escape(name)),
            '{} × {} = {} UZS'.format(quantity, _money(unit_price), _money(line_total)),
        ))
    return OrdersMessage('\n'.join(lines))


def _product_name(basket, language):
    primary = basket.product_name_ru if language == 'ru' else basket.product_name_uz
    secondary = basket.product_name_uz if language == 'ru' else basket.product_name_ru
    if primary or secondary:
        return primary or secondary
    product = basket.product
    if product:
        return (product.name_ru if language == 'ru' else product.name_uz) or (
            product.name_uz if language == 'ru' else product.name_ru
        ) or message(language, 'product')
    return message(language, 'product')


def _active_link(chat):
    return bool(
        chat and chat.is_active and chat.user_id and chat.user.is_active
        and chat.user.deleted_at is None
    )


def _status(language, prefix, value):
    key = '{}_{}'.format(prefix, value)
    return message(language, key)


def _delivery(language, value):
    return message(language, 'delivery_{}'.format(value)) if value in {'dcb', 'dtu', 'pickup'} else '—'


def _money(value):
    return '{:,}'.format(int(value)).replace(',', ' ')
