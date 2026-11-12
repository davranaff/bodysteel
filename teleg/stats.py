"""Sales report for staff: the same numbers as the old /day … /year text, as a widget card."""
import datetime

from django.db.models import Sum
from django.utils import timezone

from store.models import Basket
from teleg.cards import PERIOD_BUTTONS
from telegram_widgets.state import clip, fits


PERIODS = {'d': (1, 'последний день'), 'w': (7, 'последнюю неделю'), 'm': (30, 'последний месяц'), 'y': (365, 'последний год')}


def period_state(code):
    days, title = PERIODS[code]
    end = timezone.now()
    return report_state(end - datetime.timedelta(days=days), end, 'за {}'.format(title))


def report_state(start, end, title):
    """At most 1024 bytes: the best sellers first, the rest counted in the last line."""
    rows = list(Basket.objects.filter(
        created_at__gte=start, created_at__lte=end, order__isnull=False,
    ).values('product__name_ru').annotate(
        total_quantity=Sum('quantity'), total_sum=Sum('price'),
    ).order_by('-total_sum'))
    revenue = sum(int(row['total_sum'] or 0) for row in rows)
    head = [
        '~{} — {}'.format(timezone.localtime(start).strftime('%d.%m.%Y'), timezone.localtime(end).strftime('%d.%m.%Y')),
        '!Позиций: {} · Сумма: {} UZS'.format(len(rows), _money(revenue)),
    ]
    state = {'h': '📊 Продажи {}'.format(title), 't': head, 'b': PERIOD_BUTTONS}
    if not rows:
        state['t'] = head + ['Никакой покупки нет.']
        return state
    lines = ['{} · {} шт. · {} UZS'.format(
        clip(row['product__name_ru'] or 'Товар удалён', 48), int(row['total_quantity'] or 0), _money(row['total_sum'] or 0),
    ) for row in rows]
    shown = len(lines)
    while True:
        tail = ['~… и ещё {} поз.'.format(len(lines) - shown)] if shown < len(lines) else []
        state['t'] = head + ['-'] + lines[:shown] + tail
        if fits(state) or shown == 0:
            return state
        shown -= 1


def _money(value):
    return '{:,}'.format(int(value)).replace(',', ' ')
