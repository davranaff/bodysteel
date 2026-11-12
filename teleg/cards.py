"""Staff widget cards: the order alert, the review alert and the sales report."""
from html import unescape

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from store.geocoding.map_links import order_map_links
from store.models import Order
from telegram_widgets.html import WidgetTooLarge, render
from telegram_widgets.state import clip


LABELS = {
    'wait': 'Секунду…', 'err': 'Не получилось. Попробуйте ещё раз.',
    'RATE_LIMITED': 'Слишком часто. Подождите пару секунд.', 'TIMEOUT': 'Бот не ответил. Попробуйте ещё раз.',
    'BUSY': 'Подождите, предыдущий запрос ещё выполняется.', 'NOT_ALLOWED': 'Недоступно в этом чате.',
    'FAILED': 'Не получилось. Проверьте связь.',
}
PERIOD_BUTTONS = [['День', 'S:d'], ['Неделя', 'S:w'], ['Месяц', 'S:m'], ['Год', 'S:y']]


# A widget is at most 600 px tall and never scrolls: the rest is in the admin.
MAXIMUM_CARD_ITEMS = 8


def order_card_html(order, baskets, coupon=None, paid=False, cash_on_delivery=False):
    """The order alert as a static widget. Long orders drop items until it fits."""
    baskets = list(baskets)
    for shown in range(min(len(baskets), MAXIMUM_CARD_ITEMS), -1, -1):
        try:
            return render('card', LABELS, _order_card(order, baskets, coupon, paid, cash_on_delivery, shown))
        except WidgetTooLarge:
            continue
    raise WidgetTooLarge('order card does not fit')


def review_card_html(review):
    lines = [
        '!{}'.format(clip(review.get('product') or 'Товар', 120)),
        '~{} {} · {}'.format(review.get('first_name') or '', review.get('last_name') or '', review.get('phone') or ''),
        clip(review.get('comment') or '', 600),
        '~Опубликуйте или отклоните отзыв в админке: Магазин → Отзывы.',
    ]
    state = {'h': '💬 Новый отзыв на модерации', 't': lines}
    admin = _admin_url('store_review_changelist')
    if admin:
        state['u'] = [['Открыть отзывы', admin]]
    return render('card', LABELS, state)


def stats_html(state):
    return render('card', LABELS, state)


def _order_card(order, baskets, coupon, paid, cash_on_delivery, shown):
    created = timezone.localtime(order.created_at).strftime('%d.%m.%Y · %H:%M')
    delivery = dict(Order.DELIVERY_CHOICES).get(order.type, order.type or '—')
    lines = []
    if paid:
        lines.append('!✅ ОПЛАЧЕН ОНЛАЙН · Multicard')
    if cash_on_delivery:
        lines.append('!💵 ОПЛАТА ПРИ ПОЛУЧЕНИИ')
    lines += ['~№ {} · {}'.format(order.order_code, created), '-', '!👤 {}'.format(order.full_name or '—'),
              '={}'.format(order.phone or '—'), '-', '!🚚 {}'.format(delivery)]
    if order.address:
        lines.append('={}'.format(order.address))
    label = (getattr(order, 'address_label', '') or '').strip()
    if label and label.casefold() != (order.address or '').strip().casefold():
        lines.append('~🏷 {}'.format(label))
    lines += ['-', '!📦 Товары · {}'.format(len(baskets))]
    for index, basket in enumerate(baskets[:shown], start=1):
        name = getattr(basket.product, 'name_ru', None) or 'Товар удалён'
        quantity, total = int(basket.quantity), int(basket.price)
        unit = total // quantity if quantity else total
        lines += ['{}. {}'.format(index, name), '~{} шт. × {} = {} UZS'.format(quantity, _money(unit), _money(total))]
    if shown < len(baskets):
        lines.append('~… ещё {} поз. — подробности в админке'.format(len(baskets) - shown))
    note = getattr(order, 'customer_note', '') or ''
    if note:
        lines += ['-', '~📝 {}'.format(clip(note, 300))]
    if coupon:
        lines.append('~🏷 Купон {} · −{}%'.format(coupon.code, coupon.discount_percent))
    lines += ['-', '!💰 ИТОГО: {} UZS'.format(_money(order.total_price))]
    state = {'h': '🛒 Новый заказ', 't': [unescape(line) for line in lines],
             'c': [['📞 Скопировать телефон', order.phone]] if order.phone else []}
    links = order_map_links(order)
    urls = [['🗺 Google Maps', links.google], ['🗺 Яндекс Карты', links.yandex]] if links else []
    admin = _admin_url('store_order_change', order.pk)
    if admin:
        urls.append(['Открыть в админке', admin])
    state['u'] = [[title, url] for title, url in urls if url and len(url) <= 256]
    return state


def _admin_url(name, *args):
    origin = (getattr(settings, 'CUSTOMER_TELEGRAM_PUBLIC_ORIGIN', '') or '').rstrip('/')
    if not origin.startswith('https://'):
        return ''
    try:
        return origin + reverse('bodysteel_admin:{}'.format(name), args=args)
    except NoReverseMatch:
        return ''


def _money(value):
    return '{:,}'.format(int(value)).replace(',', ' ')
