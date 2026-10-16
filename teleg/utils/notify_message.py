import logging
from html import escape

from django.utils import timezone

from store.geocoding.map_links import order_map_links
from store.models import Order
from teleg.models import Chat as ChatModel
from teleg.views import bot


logger = logging.getLogger(__name__)
TELEGRAM_MESSAGE_LIMIT = 3900


def notify_message(order, baskets, coupon=None):
    text = format_order_notification(order, baskets, coupon)
    chat_ids = ChatModel.objects.values_list('chat_id', flat=True).distinct()
    delivered = 0
    failed = 0

    for recipient_number, chat_id in enumerate(chat_ids, start=1):
        try:
            message = bot.send_message(chat_id, text=text, parse_mode='HTML')
            delivered += 1
        except Exception:
            failed += 1
            logger.exception(
                'Telegram order notification failed',
                extra={
                    'order_id': order.pk,
                    'recipient_number': recipient_number,
                },
            )
            continue
        _send_delivery_venue(chat_id, order, message, recipient_number)

    if failed and not delivered:
        raise RuntimeError('Telegram order notification failed for every recipient')


def format_order_notification(order, baskets, coupon=None):
    baskets = list(baskets)
    delivery = dict(Order.DELIVERY_CHOICES).get(order.type, order.type or '—')
    created_at = timezone.localtime(order.created_at).strftime('%d.%m.%Y · %H:%M')
    header = (
        '🛒 <b>НОВЫЙ ЗАКАЗ</b>\n'
        f'<b>№ {escape(str(order.order_code))}</b>  ·  {created_at}\n\n'
        '👤 <b>Покупатель</b>\n'
        f'{escape(order.full_name or "—")}\n'
        f'📞 {escape(order.phone or "—")}\n\n'
        '🚚 <b>Доставка</b>\n'
        f'{escape(str(delivery))}\n'
        f'📍 {escape(order.address or "—")}\n'
        f'{_location_lines(order)}\n'
        f'📦 <b>Товары · {len(baskets)}</b>\n'
    )
    coupon_line = ''
    if coupon:
        coupon_line = (
            '\n🏷 <b>Купон:</b> '
            f'<code>{escape(coupon.code)}</code> · −{coupon.discount_percent}%\n'
        )
    footer = (
        f'{coupon_line}\n💰 <b>ИТОГО: {_money(order.total_price)} UZS</b>'
    )

    item_blocks = []
    hidden_items = 0
    for index, basket in enumerate(baskets, start=1):
        block = _basket_block(index, basket)
        reserved = len(header) + len(footer) + len(''.join(item_blocks))
        if reserved + len(block) > TELEGRAM_MESSAGE_LIMIT:
            hidden_items = len(baskets) - index + 1
            break
        item_blocks.append(block)

    if hidden_items:
        item_blocks.append(f'\n<i>… ещё {hidden_items} поз. — подробности в админке</i>\n')

    return header + ''.join(item_blocks) + footer


def _location_lines(order):
    lines = ''
    label = (getattr(order, 'address_label', '') or '').strip()
    address = (getattr(order, 'address', '') or '').strip()
    # The map label often equals the prefilled address; repeat it only when it adds detail.
    if label and label.casefold() != address.casefold():
        lines += f'🏷 {escape(label)}\n'
    links = order_map_links(order)
    if links:
        lines += (
            f'🗺 <a href="{escape(links.google)}">Открыть на карте</a>'
            f' · <a href="{escape(links.yandex)}">Яндекс Карты</a>\n'
        )
    return lines


def _send_delivery_venue(chat_id, order, message, recipient_number):
    """Pin the delivery point under the order message; never fails the order."""
    latitude = getattr(order, 'address_latitude', None)
    longitude = getattr(order, 'address_longitude', None)
    if latitude is None or longitude is None:
        return
    try:
        bot.send_venue(
            chat_id,
            float(latitude),
            float(longitude),
            title=getattr(order, 'address_label', '') or 'Адрес доставки',
            address=order.address or '',
            reply_to_message_id=message.message_id,
        )
    except Exception:
        logger.exception(
            'Telegram order venue failed',
            extra={'order_id': order.pk, 'recipient_number': recipient_number},
        )


def _basket_block(index, basket):
    product_name = getattr(basket.product, 'name_ru', None) or 'Товар удалён'
    quantity = int(basket.quantity)
    line_total = int(basket.price)
    unit_price = line_total // quantity if quantity else line_total
    return (
        f'\n<b>{index}. {escape(product_name)}</b>\n'
        f'<code>{quantity} шт. × {_money(unit_price)} = {_money(line_total)} UZS</code>\n'
    )


def _money(value):
    return f'{int(value):,}'.replace(',', ' ')
