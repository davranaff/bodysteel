import logging
from html import escape

from django.utils import timezone

from store.geocoding.map_links import order_map_links
from store.models import Order
from teleg.cards import order_card_html
from teleg.models import Chat as ChatModel
from teleg.views import bot
from teleg.widget_api import StaffWidgetError, send_widget
from telegram_widgets.html import WidgetTooLarge
from telegram_widgets.rollout import widgets_enabled


logger = logging.getLogger(__name__)
TELEGRAM_MESSAGE_LIMIT = 3900
PAID_LINE = '✅ <b>ОПЛАЧЕН ОНЛАЙН</b> · Multicard\n'
CASH_LINE = '💵 <b>ОПЛАТА ПРИ ПОЛУЧЕНИИ</b> · старая версия приложения\n'


def notify_message(order, baskets, coupon=None, paid=False, cash_on_delivery=False):
    baskets = list(baskets)
    text = format_order_notification(order, baskets, coupon, paid=paid, cash_on_delivery=cash_on_delivery)
    widget = _order_widget(order, baskets, coupon, paid, cash_on_delivery)
    chat_ids = ChatModel.objects.values_list('chat_id', flat=True).distinct()
    delivered = 0
    failed = 0

    for recipient_number, chat_id in enumerate(chat_ids, start=1):
        if widget and widgets_enabled(chat_id) and _send_widget(chat_id, widget, order, recipient_number):
            delivered += 1
            continue
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


def _order_widget(order, baskets, coupon, paid, cash_on_delivery):
    try:
        html = order_card_html(order, baskets, coupon, paid=paid, cash_on_delivery=cash_on_delivery)
    except WidgetTooLarge:
        return None
    caption = '{} № {} · {} UZS'.format('✅ Оплачен заказ' if paid else '🛒 Новый заказ',
                                       escape(str(order.order_code)), _money(order.total_price))
    return html, caption


def _send_widget(chat_id, widget, order, recipient_number):
    """The order as a widget card; on any refusal the text message goes instead."""
    html, caption = widget
    try:
        send_widget(chat_id, html, caption)
    except StaffWidgetError as error:
        logger.warning('Staff order widget refused (%s), sending text', error.code or 'no code', extra={
            'order_id': order.pk, 'recipient_number': recipient_number,
        })
        return False
    return True


def format_order_notification(order, baskets, coupon=None, paid=False, cash_on_delivery=False):
    baskets = list(baskets)
    delivery = dict(Order.DELIVERY_CHOICES).get(order.type, order.type or '—')
    created_at = timezone.localtime(order.created_at).strftime('%d.%m.%Y · %H:%M')
    header = (
        '🛒 <b>НОВЫЙ ЗАКАЗ</b>\n'
        f'{PAID_LINE if paid else ""}'
        f'{CASH_LINE if cash_on_delivery else ""}'
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
