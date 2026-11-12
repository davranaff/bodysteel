"""Bot API calls for staff widgets (Bot API 10.4); pyTelegramBotAPI does not know them yet."""
import json
import logging

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)
API_ORIGIN = 'https://api.telegram.org'
MAXIMUM_RESPONSE_BYTES = 64 * 1024


class StaffWidgetError(Exception):
    """Telegram refused or could not be reached; callers fall back to a text message."""


def send_widget(chat_id, html, caption, chat_data=None, allow_queries=False, client=None):
    payload = {'chat_id': chat_id, 'html': html, 'caption': caption, 'parse_mode': 'HTML'}
    if chat_data is not None:
        payload['chat_data'] = chat_data
    if allow_queries:
        payload['allow_queries'] = True
    result = call('sendWidget', payload, client)
    message_id = result.get('message_id') if isinstance(result, dict) else None
    if not isinstance(message_id, int):
        raise StaffWidgetError('sendWidget returned no message')
    return message_id


def answer_widget_query(query_id, data=None, client=None):
    payload = {'widget_query_id': query_id}
    if data is not None:
        payload['data'] = data
    return call('answerWidgetQuery', payload, client)


def edit_widget_data(chat_id, message_id, chat_data, client=None):
    return call('editMessageWidgetData', {'chat_id': chat_id, 'message_id': message_id, 'chat_data': chat_data}, client)


def call(method, payload, client=None):
    token = settings.BOT_TOKEN
    if not token:
        raise StaffWidgetError('staff bot token is not configured')
    owned = client is None
    client = client or httpx.Client(follow_redirects=False, timeout=httpx.Timeout(5.0, connect=2.0))
    try:
        response = client.post('{}/bot{}/{}'.format(API_ORIGIN, token, method), json=payload)
        body = response.content[:MAXIMUM_RESPONSE_BYTES + 1]
    except httpx.HTTPError as error:
        raise StaffWidgetError('Telegram is unreachable') from error
    finally:
        if owned:
            client.close()
    try:
        data = json.loads(body.decode('utf-8')) if len(body) <= MAXIMUM_RESPONSE_BYTES else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = None
    if not isinstance(data, dict) or data.get('ok') is not True:
        # The description can echo request content; never log it.
        raise StaffWidgetError('{} failed with HTTP {}'.format(method, response.status_code))
    return data.get('result')
