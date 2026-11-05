"""Server-to-server transport for the Multicard payment gateway.

The bearer token is cached for its lifetime (Multicard asks partners not to
request one per call) and refreshed once on ``401``. Responses are bounded and
redirects are never followed. Nothing here logs credentials or bodies.
"""
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone

import httpx
from django.core.cache import cache as default_cache
from django.utils import timezone


MAXIMUM_RESPONSE_BYTES = 256 * 1024
TOKEN = re.compile(r'^[A-Za-z0-9._~+/=-]{16,4096}$')
UUID = re.compile(r'^[0-9a-fA-F-]{36}$')
TASHKENT = dt_timezone(timedelta(hours=5))
TOKEN_REFRESH_MARGIN = timedelta(minutes=10)
FALLBACK_TOKEN_SECONDS = 23 * 3600
PAYMENT_STATUSES = {'draft', 'progress', 'billing', 'success', 'error', 'revert', 'hold'}


class MulticardUnavailable(Exception):
    """Multicard could not be reached or returned an unusable response."""


class MulticardRejected(Exception):
    """Multicard answered ``success: false`` with a stable error code."""

    def __init__(self, code, details=''):
        super().__init__('Multicard rejected the request')
        self.code = code if isinstance(code, str) else 'unknown'
        self.details = details if isinstance(details, str) else ''


@dataclass(frozen=True)
class Invoice:
    uuid: str
    checkout_url: str
    payment_status: str
    payment_uuid: str | None


class MulticardClient:
    def __init__(self, configuration, http=None, cache=None):
        self._configuration = configuration
        self._http = http or httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(configuration.timeout_seconds, connect=min(5.0, configuration.timeout_seconds)),
            trust_env=False,
        )
        self._cache = cache or default_cache

    def create_invoice(self, body):
        return _parse_invoice(self._authorized('POST', '/payment/invoice', body))

    def get_invoice(self, invoice_uuid):
        return _parse_invoice(self._authorized('GET', '/payment/invoice/{}'.format(_uuid(invoice_uuid)), None))

    def cancel_invoice(self, invoice_uuid):
        self._authorized('DELETE', '/payment/invoice/{}'.format(_uuid(invoice_uuid)), None)

    def _authorized(self, method, path, body):
        for attempt in range(2):
            token = self._token(refresh=attempt > 0)
            status, payload = self._send(method, path, body, token)
            if status == 401 and attempt == 0:
                continue
            return _unwrap(status, payload)
        raise MulticardUnavailable('unauthorized')

    def _token(self, refresh=False):
        key = self._cache_key()
        if not refresh:
            cached = self._cache.get(key)
            if isinstance(cached, str) and TOKEN.fullmatch(cached):
                return cached
        configuration = self._configuration
        status, payload = self._send('POST', '/auth', {
            'application_id': configuration.application_id,
            'secret': configuration.secret,
        }, None)
        if status != 200 or not isinstance(payload, dict):
            raise MulticardUnavailable('auth status {}'.format(status))
        token = payload.get('token')
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise MulticardUnavailable('auth token')
        self._cache.set(key, token, _token_lifetime(payload.get('expiry')))
        return token

    def _cache_key(self):
        configuration = self._configuration
        scope = '{}|{}'.format(configuration.base_url, configuration.application_id).encode()
        return 'payments:multicard:token:{}'.format(hashlib.sha256(scope).hexdigest()[:24])

    def _send(self, method, path, body, token):
        headers = {'Accept': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer {}'.format(token)
        content = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            content = json.dumps(body, ensure_ascii=False).encode('utf-8')
        try:
            with self._http.stream(
                method, '{}{}'.format(self._configuration.base_url, path), content=content, headers=headers,
            ) as response:
                raw = _read_bounded(response)
                status = response.status_code
        except httpx.HTTPError:
            raise MulticardUnavailable('transport failed') from None
        if 300 <= status < 400:
            raise MulticardUnavailable('redirect')
        try:
            return status, json.loads(raw) if raw else None
        except ValueError:
            if status >= 500:
                raise MulticardUnavailable('status {}'.format(status)) from None
            raise MulticardUnavailable('invalid JSON') from None


def _read_bounded(response):
    chunks = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > MAXIMUM_RESPONSE_BYTES:
            raise MulticardUnavailable('response too large')
        chunks.append(chunk)
    return b''.join(chunks)


def _unwrap(status, payload):
    if status >= 500 or not isinstance(payload, dict):
        raise MulticardUnavailable('status {}'.format(status))
    if payload.get('success') is True and 200 <= status < 300:
        return payload.get('data')
    error = payload.get('error') if isinstance(payload.get('error'), dict) else {}
    if payload.get('success') is False or 400 <= status < 500:
        raise MulticardRejected(error.get('code', 'unknown'), error.get('details', ''))
    raise MulticardUnavailable('status {}'.format(status))


def _parse_invoice(data):
    if not isinstance(data, dict):
        raise MulticardUnavailable('invalid invoice')
    invoice_uuid = data.get('uuid')
    checkout_url = data.get('checkout_url')
    if not isinstance(invoice_uuid, str) or not UUID.fullmatch(invoice_uuid):
        raise MulticardUnavailable('invalid invoice uuid')
    if not isinstance(checkout_url, str) or not checkout_url.startswith('https://') or len(checkout_url) > 2048:
        raise MulticardUnavailable('invalid checkout url')
    payment = data.get('payment') if isinstance(data.get('payment'), dict) else {}
    status = payment.get('status')
    payment_uuid = payment.get('uuid')
    return Invoice(
        uuid=invoice_uuid,
        checkout_url=checkout_url,
        payment_status=status if status in PAYMENT_STATUSES else 'draft',
        payment_uuid=payment_uuid if isinstance(payment_uuid, str) and UUID.fullmatch(payment_uuid) else None,
    )


def _uuid(value):
    if not isinstance(value, str) or not UUID.fullmatch(value):
        raise ValueError('invalid invoice uuid')
    return value


def _token_lifetime(expiry):
    """Seconds to cache a token whose ``expiry`` is ``YYYY-mm-dd HH:MM:SS`` in GMT+5."""
    try:
        expires_at = datetime.strptime(expiry, '%Y-%m-%d %H:%M:%S').replace(tzinfo=TASHKENT)
    except (TypeError, ValueError):
        return FALLBACK_TOKEN_SECONDS
    seconds = int((expires_at - TOKEN_REFRESH_MARGIN - timezone.now()).total_seconds())
    return max(60, min(seconds, FALLBACK_TOKEN_SECONDS))
