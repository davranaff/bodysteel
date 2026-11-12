"""Staff bot replies as widget cards, with the plain text as the fallback."""
import logging

from teleg.cards import LABELS, stats_html
from teleg.widget_api import StaffWidgetError, answer_widget_query, edit_widget_data, send_widget
from telegram_widgets.html import WidgetTooLarge, render
from telegram_widgets.rollout import widgets_enabled
from telegram_widgets.state import clip, encode, fits


logger = logging.getLogger(__name__)


def reply(bot, chat_id, text, links=None):
    """Send ``text`` (and ``[title, url]`` link buttons) as a card, else as a message."""
    if not widgets_enabled(chat_id):
        bot.send_message(chat_id, text)
        return
    lines = [line for line in text.split('\n') if line.strip()]
    state = {'t': lines}
    if links:
        state['u'] = links
    try:
        send_widget(chat_id, render('card', LABELS, state), clip(lines[0] if lines else '', 200))
        return
    except (StaffWidgetError, WidgetTooLarge):
        logger.warning('Staff card refused, sending text')
    bot.send_message(chat_id, text)


def send_report(bot, chat_id, state):
    """The sales report widget; its period buttons come back as widget queries."""
    if not widgets_enabled(chat_id):
        bot.send_message(chat_id, _report_text(state))
        return
    try:
        send_widget(chat_id, stats_html(state), clip(state['h'], 200), chat_data=encode(state), allow_queries=True)
        return
    except (StaffWidgetError, WidgetTooLarge):
        logger.warning('Staff report widget refused, sending text')
    bot.send_message(chat_id, _report_text(state))


def _report_text(state):
    return '\n'.join([state['h']] + [line.lstrip('!~') for line in state['t'] if line != '-'])


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
