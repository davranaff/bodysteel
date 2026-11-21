import logging
from html import escape

from django.utils import timezone
from telebot import types

from store.geocoding.map_links import order_map_links
from store.models import Order
from teleg.cards import admin_link, order_card_html
from teleg.models import Chat as ChatModel
from teleg.views import bot
from teleg.widget_api import StaffWidgetError, send_widget
from telegram_widgets.html import WidgetTooLarge
from telegram_widgets.rollout import widgets_enabled


logger = logging.getLogger(__name__)
TELEGRAM_MESSAGE_LIMIT = 3900
PAID_LINE = '✅ <b>Оплачен онлайн</b> · Multicard'
PENDING_LINE = '⏳ <b>Ждёт онлайн-оплаты</b>'
CASH_LINE = '💵 <b>Оплата при получении</b>'
NOTE_LIMIT = 500


def notify_message(order, baskets, coupon=None, paid=False, cash_on_delivery=False):
    baskets = list(baskets)
    text = format_order_notification(order, baskets, coupon, paid=paid, cash_on_delivery=cash_on_delivery)
    buttons = order_buttons(order)
    widget = _order_widget(order, baskets, coupon, paid, cash_on_delivery)
    chat_ids = ChatModel.objects.values_list('chat_id', flat=True).distinct()
    delivered = 0
    failed = 0

    for recipient_number, chat_id in enumerate(chat_ids, start=1):
        if widget and widgets_enabled(chat_id) and _send_widget(chat_id, widget, order, recipient_number):
            delivered += 1
            continue
        try:
            message = bot.send_message(chat_id, text=text, parse_mode='HTML', reply_markup=buttons)
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
    """The order as an HTML message: who, where, what, how much. Items go in a quote."""
    baskets = list(baskets)
    delivery = dict(Order.DELIVERY_CHOICES).get(order.type, order.type or '—')
    created_at = timezone.localtime(order.created_at).strftime('%d.%m.%Y · %H:%M')
    header = '\n'.join(line for line in (
        '🛒 <b>Новый заказ № {}</b>'.format(escape(str(order.order_code))),
        '<i>{}</i>'.format(created_at),
        '',
        _payment_line(order, paid, cash_on_delivery),
        '',
        '👤 <b>{}</b>'.format(escape(order.full_name or '—')),
        '📞 {}'.format(escape(order.phone or '—')),
        '',
        '🚚 <b>{}</b>'.format(escape(str(delivery))),
        *_place_lines(order),
        '',
        '📦 <b>Товары · {}</b>'.format(len(baskets)),
    ) if line is not None) + '\n'
    footer = _footer(order, coupon)

    item_blocks = []
    hidden_items = 0
    for index, basket in enumerate(baskets, start=1):
        block = _basket_block(index, basket)
        reserved = len(header) + len(footer) + len(''.join(item_blocks)) + len('<blockquote></blockquote>')
        if reserved + len(block) > TELEGRAM_MESSAGE_LIMIT:
            hidden_items = len(baskets) - index + 1
            break
        item_blocks.append(block)
    items = '<blockquote>{}</blockquote>'.format('\n\n'.join(item_blocks)) if item_blocks else ''
    if hidden_items:
        items += '\n<i>… ещё {} поз. — полный список в админке</i>'.format(hidden_items)
    return header + items + footer


def order_buttons(order):
    """Map and admin links as buttons under the text message."""
    rows = []
    links = order_map_links(order)
    if links:
        rows.append([
            types.InlineKeyboardButton('🗺 Google Maps', url=links.google),
            types.InlineKeyboardButton('🗺 Яндекс Карты', url=links.yandex),
        ])
    admin = admin_link('store_order_change', order.pk)
    if admin:
        rows.append([types.InlineKeyboardButton('Открыть в админке', url=admin)])
    if not rows:
        return None
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        markup.row(*row)
    return markup


def _payment_line(order, paid, cash_on_delivery):
    if paid or getattr(order, 'payment_status', '') == 'paid':
        return PAID_LINE
    if not cash_on_delivery and getattr(order, 'payment_status', '') == 'pending':
        return PENDING_LINE
    # Everything else is announced when it is placed, so it is paid on delivery.
    return CASH_LINE


def _place_lines(order):
    address = (getattr(order, 'address', '') or '').strip()
    label = (getattr(order, 'address_label', '') or '').strip()
    lines = ['📍 {}'.format(escape(address))] if address else []
    # The map label often equals the prefilled address; repeat it only when it adds detail.
    if label and label.casefold() != address.casefold():
        lines.append('🏷 {}'.format(escape(label)))
    slot = _slot(order)
    if slot:
        lines.append('🕑 {}'.format(escape(slot)))
    return lines


def _slot(order):
    day = getattr(order, 'delivery_slot_date', None)
    label = (getattr(order, 'delivery_slot_label', '') or '').strip()
    return ' · '.join(value for value in (day.strftime('%d.%m.%Y') if day else '', label) if value)


def _footer(order, coupon):
    lines = []
    note = ' '.join((getattr(order, 'customer_note', '') or '').split())
    if note:
        lines += ['', '📝 <i>{}</i>'.format(escape(note[:NOTE_LIMIT]))]
    lines.append('')
    discount = int(getattr(order, 'discount_price', 0) or 0)
    parts = ['−{} UZS'.format(_money(discount))] if discount else []
    if coupon:
        parts.append('купон <code>{}</code> −{}%'.format(escape(coupon.code), coupon.discount_percent))
    if parts:
        lines.append('🏷 Скидка: {}'.format(' · '.join(parts)))
    fee = int(getattr(order, 'delivery_fee', 0) or 0)
    if fee:
        lines.append('Доставка: {} UZS'.format(_money(fee)))
    lines.append('💰 <b>Итого: {} UZS</b>'.format(_money(order.total_price)))
    return '\n'.join(lines)


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
    return '{}. <b>{}</b>\n{} шт. × {} = {} UZS'.format(
        index, escape(product_name), quantity, _money(unit_price), _money(line_total),
    )


def _money(value):
    return f'{int(value):,}'.replace(',', ' ')
