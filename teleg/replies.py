"""Staff bot replies as widget cards, with the HTML text message as the fallback."""
import logging
import re
from html import escape, unescape

from teleg.cards import LABELS, stats_html
from teleg.widget_api import StaffWidgetError, answer_widget_query, edit_widget_data, send_widget
from telegram_widgets.html import WidgetTooLarge, render
from telegram_widgets.rollout import widgets_enabled
from telegram_widgets.state import clip, encode, fits
from telebot import types


logger = logging.getLogger(__name__)
TAG = re.compile(r'<[^>]+>')


def reply(bot, chat_id, text, links=None):
    """Send ``text`` (and ``[title, url]`` link buttons) as a card, else as a message."""
    if not widgets_enabled(chat_id):
        _send_text(bot, chat_id, text, links)
        return
    lines = [unescape(TAG.sub('', line)) for line in text.split('\n') if line.strip()]
    state = {'t': lines}
    if links:
        state['u'] = links
    try:
        send_widget(chat_id, render('card', LABELS, state), clip(lines[0] if lines else '', 200))
        return
    except (StaffWidgetError, WidgetTooLarge) as error:
        logger.warning('Staff card refused (%s), sending text', getattr(error, 'code', '') or 'no code')
    _send_text(bot, chat_id, text, links)


def _send_text(bot, chat_id, text, links=None):
    markup = None
    if links:
        markup = types.InlineKeyboardMarkup()
        for title, url in links:
            markup.row(types.InlineKeyboardButton(title, url=url))
    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)


def send_report(bot, chat_id, state):
    """The sales report widget; its period buttons come back as widget queries."""
    if not widgets_enabled(chat_id):
        bot.send_message(chat_id, report_text(state), parse_mode='HTML')
        return
    try:
        send_widget(chat_id, stats_html(state), clip(state['h'], 200), chat_data=encode(state), allow_queries=True)
        return
    except (StaffWidgetError, WidgetTooLarge) as error:
        logger.warning('Staff report widget refused (%s), sending text', getattr(error, 'code', '') or 'no code')
    bot.send_message(chat_id, report_text(state), parse_mode='HTML')


def report_text(state):
    """The report card as HTML: the period and totals on top, the products in a quote."""
    head, rows, seen_rows = ['<b>{}</b>'.format(escape(state['h']))], [], False
    for line in state['t']:
        if line == '-':
            seen_rows = True
            continue
        if line.startswith('~'):
            value = '<i>{}</i>'.format(escape(line[1:]))
        elif line.startswith('!'):
            value = '<b>{}</b>'.format(escape(line[1:]))
        elif seen_rows:
            # "name · 2 шт. · 300 000 UZS": the name in bold, the numbers under it.
            name, _, numbers = line.partition(' · ')
            value = '<b>{}</b>\n{}'.format(escape(name), escape(numbers)) if numbers else escape(line)
        else:
            value = escape(line)
        (rows if seen_rows else head).append(value)
    if rows:
        head += ['', '<blockquote>{}</blockquote>'.format('\n'.join(rows))]
    return '\n'.join(head)


def answer_report(query, state):
    if not fits(state):
        answer_widget_query(query['id'])
        return
    data = encode(state)
    answer_widget_query(query['id'], data)
    try:
        edit_widget_data(query['chat']['id'], query['message_id'], data)
    except StaffWidgetError:
        logger.warning('Staff report state was not saved')
