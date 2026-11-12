"""Period buttons of the staff sales report: only verified staff chats get numbers."""
import logging
import re

from teleg.models import Chat as ChatModel
from teleg.replies import answer_report
from teleg.stats import period_state
from teleg.widget_api import StaffWidgetError, answer_widget_query


logger = logging.getLogger(__name__)
REQUEST = re.compile(r'^S:([dwmy])$')


def handle_staff_widget_query(query):
    if not isinstance(query, dict) or not isinstance(query.get('id'), str):
        return 'ignored'
    try:
        return _handle(query)
    except StaffWidgetError:
        logger.warning('Staff widget query could not be answered')
        return 'failed'


def _handle(query):
    sender, chat = query.get('from'), query.get('chat')
    data = query.get('data')
    allowed = (
        isinstance(sender, dict) and isinstance(chat, dict) and chat.get('type') == 'private'
        and isinstance(sender.get('id'), int) and sender.get('id') == chat.get('id')
        and isinstance(query.get('message_id'), int) and isinstance(data, str)
        and ChatModel.objects.filter(chat_id=str(chat.get('id'))).exists()
    )
    match = REQUEST.fullmatch(data) if allowed else None
    if not match:
        answer_widget_query(query['id'])
        return 'denied'
    answer_report(query, period_state(match.group(1)))
    return 'answered'
