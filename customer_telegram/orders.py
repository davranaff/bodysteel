from dataclasses import dataclass
from html import escape

from django.db.models import Q
from django.utils import timezone

from customer_telegram.i18n import message
from customer_telegram.keyboards import orders_keyboard
from store.models import Order


# Four orders keep the card under a widget's 600 px height.
PAGE_SIZE = 4
# Telegram allows 4096 characters; long orders end with "and N more".
DETAIL_LIMIT = 3600
PAYMENT_ICONS = {'unpaid': '💵', 'pending': '⏳', 'paid': '💳', 'failed': '⚠️', 'refunded': '↩️'}
FULFILLMENT_ICONS = {
    'new': '🆕', 'confirmed': '✔️', 'preparing': '📦', 'ready': '🏬',
    'delivering': '🚚', 'delivered': '✅', 'cancelled': '✖️',
}


@dataclass(frozen=True)
class OrdersMessage:
    text: str
    reply_markup: dict | None = None


def visible_orders(chat):
    """Orders of the linked account plus the ones placed in this chat."""
    placed_here = Q(customer_telegram_widgets__chat=chat)
    if _active_link(chat):
        return Order.objects.filter(Q(user=chat.user) | placed_here).distinct()
    return Order.objects.filter(placed_here).distinct()


def orders_page(chat, page):
    if not isinstance(page, int) or not 0 <= page <= 10_000:
        return OrdersMessage(message(chat.language or 'ru', 'not_linked'))
    if not _active_link(chat) and not visible_orders(chat).exists():
        return OrdersMessage(message(chat.language or 'ru', 'not_linked'))
    language = chat.language or 'ru'
    offset = page * PAGE_SIZE
    orders = list(visible_orders(chat).only(
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
            '<b>№ {}</b> · {}'.format(escape(order.order_code), created),
            '{} · {}'.format(_fulfillment(language, order), _status(language, 'payment', order.payment_status)),
            '<b>{}</b>'.format(_sum(language, order.total_price)),
        ))
    keyboard = orders_keyboard(
        language, page, page > 0, has_next,
        [(order.pk, order.order_code) for order in visible],
    )
    return OrdersMessage('\n'.join(lines), keyboard)


def order_detail(chat, order_id):
    if not isinstance(order_id, int) or order_id < 1:
        return OrdersMessage(message(chat.language or 'ru', 'callback_denied'))
    order = visible_orders(chat).filter(pk=order_id).prefetch_related(
        'baskets__product',
    ).first()
    language = chat.language or 'ru'
    if not order:
        return OrdersMessage(message(language, 'callback_denied'))
    created = timezone.localtime(order.created_at).strftime('%d.%m.%Y · %H:%M')
    head = '\n'.join((
        '📦 <b>{} № {}</b>'.format(message(language, 'order'), escape(order.order_code)),
        '<i>{}</i>'.format(created),
        '',
        _fulfillment(language, order),
        '{} {}'.format(PAYMENT_ICONS.get(order.payment_status, '•'), _status(language, 'payment', order.payment_status)),
        '📍 {}'.format(_delivery(language, order.type)),
        '',
        '<b>{}</b>'.format(message(language, 'order_items')),
    ))
    total = '<b>{}: {}</b>'.format(message(language, 'order_total'), _sum(language, order.total_price))
    baskets = list(order.baskets.all())
    items = []
    for index, basket in enumerate(baskets, start=1):
        block = _item(index, basket, language)
        if len(head) + len(total) + sum(len(item) + 2 for item in items) + len(block) > DETAIL_LIMIT:
            items.append('… +{}'.format(len(baskets) - index + 1))
            break
        items.append(block)
    quote = '<blockquote>{}</blockquote>'.format('\n\n'.join(items)) if items else ''
    return OrdersMessage('\n'.join(part for part in (head, quote, total) if part))


def _item(index, basket, language):
    quantity = int(basket.quantity)
    line_total = int(basket.price)
    unit_price = int(basket.unit_price) if int(basket.unit_price) > 0 else (
        line_total // quantity if quantity else line_total
    )
    return '{}. <b>{}</b>\n{} × {} = {}'.format(
        index, escape(_product_name(basket, language)), quantity, _money(unit_price), _sum(language, line_total),
    )


def _fulfillment(language, order):
    icon = FULFILLMENT_ICONS.get(order.fulfillment_status, '•')
    return '{} {}'.format(icon, _status(language, 'fulfillment', order.fulfillment_status))


def _sum(language, value):
    return '{} {}'.format(_money(value), message(language, 'currency'))


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
