import json
import threading

import httpx

from users.auth.configuration import EskizConfiguration
from users.auth.ports import SmsDeliveryResult


ESKIZ_ORIGIN = 'https://notify.eskiz.uz'
LOGIN_URL = f'{ESKIZ_ORIGIN}/api/auth/login'
SEND_URL = f'{ESKIZ_ORIGIN}/api/message/sms/send'
MAXIMUM_RESPONSE_BYTES = 64 * 1024


class EskizSmsGateway:
    def __init__(self, configuration: EskizConfiguration, client=None):
        self.configuration = configuration
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(5.0, connect=3.0),
            follow_redirects=False,
        )
        self._token = None
        self._token_lock = threading.Lock()

    def send_otp(self, phone, code):
        token = self._access_token()
        if token is None:
            return SmsDeliveryResult.FAILED
        result, unauthorized = self._send_once(phone, code, token)
        if not unauthorized:
            return result
        self._invalidate_token(token)
        refreshed = self._access_token()
        if refreshed is None:
            return SmsDeliveryResult.FAILED
        result, _ = self._send_once(phone, code, refreshed)
        return result

    def _access_token(self):
        with self._token_lock:
            if self._token:
                return self._token
            self._token = self._login()
            return self._token

    def _login(self):
        try:
            response = self._request(
                'POST',
                LOGIN_URL,
                files=_multipart({
                    'email': self.configuration.email,
                    'password': self.configuration.password,
                }),
            )
        except httpx.TransportError:
            return None
        if response.status_code != 200 or response.oversized:
            return None
        try:
            payload = json.loads(response.content)
            token = payload['data']['token']
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return token if isinstance(token, str) and 1 <= len(token) <= 4096 else None

    def _send_once(self, phone, code, token):
        try:
            response = self._request(
                'POST',
                SEND_URL,
                files=_multipart({
                    'mobile_phone': phone.removeprefix('+'),
                    'message': self.configuration.template.replace('{code}', code),
                    'from': self.configuration.sender,
                }),
                headers={'Authorization': f'Bearer {token}'},
            )
        except httpx.TransportError:
            return SmsDeliveryResult.UNKNOWN, False
        if response.status_code == 401:
            return SmsDeliveryResult.FAILED, True
        if response.oversized:
            return SmsDeliveryResult.UNKNOWN, False
        if 200 <= response.status_code < 300:
            return SmsDeliveryResult.SENT, False
        return SmsDeliveryResult.FAILED, False

    def _request(self, method, url, **kwargs):
        with self.client.stream(method, url, **kwargs) as response:
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > MAXIMUM_RESPONSE_BYTES:
                    return _ProviderResponse(response.status_code, b'', True)
            return _ProviderResponse(response.status_code, bytes(content), False)

    def _invalidate_token(self, token):
        with self._token_lock:
            if self._token == token:
                self._token = None


class _ProviderResponse:
    def __init__(self, status_code, content, oversized):
        self.status_code = status_code
        self.content = content
        self.oversized = oversized


def _multipart(values):
    return {name: (None, value) for name, value in values.items()}
