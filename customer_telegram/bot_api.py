import json
from dataclasses import dataclass
from enum import Enum

import httpx

from customer_telegram.configuration import require_configuration


API_ORIGIN = 'https://api.telegram.org'
MAXIMUM_RESPONSE_BYTES = 64 * 1024


class DeliveryStatus(Enum):
    SENT = 'sent'
    UNKNOWN = 'unknown'
    FAILED = 'failed'
    BLOCKED = 'blocked'
    RATE_LIMITED = 'rate_limited'


@dataclass(frozen=True)
class TelegramResult:
    status: DeliveryStatus
    message_id: int | None = None
    retry_after: int | None = None


@dataclass(frozen=True)
class WebhookInfo:
    ok: bool
    url: str = ''
    pending_update_count: int = 0


class CustomerTelegramApi:
    def __init__(self, client=None):
        configuration = require_configuration()
        self._token = configuration.token
        self._client = client or httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(5.0, connect=2.0, read=5.0, write=5.0, pool=2.0),
        )

    def send_message(self, chat_id, text, reply_markup=None, parse_mode='HTML'):
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
        if reply_markup:
            payload['reply_markup'] = reply_markup
        result, data = self._call('sendMessage', payload)
        if result.status is not DeliveryStatus.SENT:
            return result
        message_id = data.get('result', {}).get('message_id')
        if not isinstance(message_id, int):
            return TelegramResult(DeliveryStatus.UNKNOWN)
        return TelegramResult(DeliveryStatus.SENT, message_id=message_id)

    def answer_callback_query(self, callback_query_id, text=None):
        payload = {'callback_query_id': callback_query_id}
        if text:
            payload['text'] = text
        return self._call('answerCallbackQuery', payload)[0]

    def set_webhook(self):
        configuration = require_configuration()
        return self._call('setWebhook', {
            'url': configuration.webhook_url,
            'secret_token': configuration.webhook_secret,
            'allowed_updates': ['message', 'callback_query'],
            'drop_pending_updates': False,
        })[0]

    def delete_webhook(self):
        return self._call('deleteWebhook', {'drop_pending_updates': False})[0]

    def set_my_commands(self, commands, language_code):
        return self._call('setMyCommands', {
            'commands': commands,
            'language_code': language_code,
            'scope': {'type': 'all_private_chats'},
        })[0]

    def get_webhook_info(self):
        result, data = self._call('getWebhookInfo', {})
        payload = data.get('result', {}) if result.status is DeliveryStatus.SENT else {}
        url = payload.get('url', '')
        pending = payload.get('pending_update_count', 0)
        return WebhookInfo(
            result.status is DeliveryStatus.SENT and isinstance(url, str) and isinstance(pending, int),
            url if isinstance(url, str) else '',
            pending if isinstance(pending, int) and pending >= 0 else 0,
        )

    def _call(self, method, payload):
        url = '{}/bot{}/{}'.format(API_ORIGIN, self._token, method)
        try:
            with self._client.stream('POST', url, json=payload) as response:
                body = _bounded_body(response)
        except (httpx.HTTPError, ValueError):
            return TelegramResult(DeliveryStatus.UNKNOWN), {}
        data = _json_object(body)
        if data is None:
            return TelegramResult(DeliveryStatus.UNKNOWN), {}
        if 200 <= response.status_code < 300 and data.get('ok') is True:
            return TelegramResult(DeliveryStatus.SENT), data
        parameters = data.get('parameters') if isinstance(data.get('parameters'), dict) else {}
        retry_after = parameters.get('retry_after')
        retry_after = retry_after if isinstance(retry_after, int) and 0 < retry_after <= 86_400 else None
        if response.status_code == 429:
            return TelegramResult(DeliveryStatus.RATE_LIMITED, retry_after=retry_after), data
        if response.status_code == 403:
            return TelegramResult(DeliveryStatus.BLOCKED), data
        if 500 <= response.status_code < 600:
            return TelegramResult(DeliveryStatus.UNKNOWN), data
        return TelegramResult(DeliveryStatus.FAILED), data


def _bounded_body(response):
    length = response.headers.get('content-length', '')
    if length.isdigit() and int(length) > MAXIMUM_RESPONSE_BYTES:
        raise ValueError('oversized response')
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > MAXIMUM_RESPONSE_BYTES:
            raise ValueError('oversized response')
    return bytes(body)


def _json_object(body):
    try:
        value = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
