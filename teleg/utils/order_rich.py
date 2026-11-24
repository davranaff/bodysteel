"""Staff order alert as a rich message (Bot API 10.3+): the items become a table in a fold.

``sendRichMessage`` takes HTML with ``<p>``, ``<details>`` and ``<table>``. When Telegram refuses it,
the alert goes out as the plain HTML message instead, and rich alerts pause for a while so every
order does not pay for a refused call first.
"""
import logging
from html import escape

from django.conf import settings
from django.core.cache import cache

from teleg.widget_api import StaffWidgetError, call


logger = logging.getLogger(__name__)
PAUSE_KEY = 'teleg:rich-orders-paused'
PAUSE_SECONDS = 30 * 60
# Up to this many lines the table opens by itself; a longer order folds so the alert stays short.
OPEN_ITEMS = 6
# Telegram counts table rows among at most 500 blocks; the rest of a huge order is in the admin.
TABLE_ROWS = 80


def rich_order_html(header, rows, footer):
    """``header``/``footer``: HTML lines with '' between groups; ``rows``: (name, quantity, line total)."""
    shown = rows[:TABLE_ROWS]
    table = ''.join(
        '<tr><td>{}</td><td align="center">{}</td><td align="right">{}</td></tr>'.format(
            escape(name), quantity, _money(total),
        )
        for name, quantity, total in shown
    )
    hidden = len(rows) - len(shown)
    rest = '<p><i>… ещё {} поз. — полный список в админке</i></p>'.format(hidden) if hidden else ''
    details = (
        '<details{}><summary>📦 <b>Товары · {}</b></summary>'
        '<table bordered striped compact><tr><th>Товар</th><th>Шт.</th><th>Сумма, UZS</th></tr>{}</table>{}'
        '</details>'
    ).format(' open' if len(rows) <= OPEN_ITEMS else '', len(rows), table, rest)
    return _paragraphs(header) + details + _paragraphs(footer)


def send_rich_order(chat_id, html, buttons, order_id, recipient_number):
    """The message id of the rich alert, or None when the plain message should go instead."""
    if not getattr(settings, 'STAFF_TELEGRAM_RICH_ORDERS', True) or cache.get(PAUSE_KEY):
        return None
    payload = {'chat_id': chat_id, 'rich_message': {'html': html}}
    if buttons is not None:
        payload['reply_markup'] = buttons.to_dict()
    try:
        result = call('sendRichMessage', payload)
    except StaffWidgetError as error:
        if error.code:
            cache.set(PAUSE_KEY, True, PAUSE_SECONDS)
        logger.warning('Staff rich order refused (%s), sending text', error.code or 'no code', extra={
            'order_id': order_id, 'recipient_number': recipient_number,
        })
        return None
    message_id = result.get('message_id') if isinstance(result, dict) else None
    return message_id if isinstance(message_id, int) else None


def _paragraphs(lines):
    groups, current = [], []
    for line in list(lines) + ['']:
        if line:
            current.append(line)
        elif current:
            groups.append('<p>{}</p>'.format('<br>'.join(current)))
            current = []
    return ''.join(groups)


def _money(value):
    return f'{int(value):,}'.replace(',', ' ')
