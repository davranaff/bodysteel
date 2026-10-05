import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from django.utils import timezone


SESSIONS_PATH = '/api/v1/integrations/widget-shopper-sessions'
MAXIMUM_RESPONSE_BYTES = 8 * 1024
ACCESS_TOKEN = re.compile(r'^[A-Za-z0-9._~-]{1,4096}$')
RETRY_AFTER_SECONDS = re.compile(r'^\d{1,6}$')
MINIMUM_REMAINING_LIFETIME = timedelta(seconds=30)


class SavdoqUnavailable(Exception):
    """SAVDOQ could not be reached or answered with an unusable response."""


class SavdoqRefused(Exception):
    """SAVDOQ refused the shopper with an actionable status (403 or 429)."""

    def __init__(self, status, retry_after=None):
        super().__init__('SAVDOQ refused the shopper session')
        self.status = status
        self.retry_after = retry_after


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    expires_at: datetime
    session_id: uuid.UUID | None


class SavdoqShopperClient:
    def __init__(self, configuration, client=None):
        self._configuration = configuration
        self._client = client or httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(8.0, connect=3.0),
            trust_env=False,
        )

    def issue(self, subject_hash, language):
        response = self._send('POST', subject_hash, language)
        if response.status_code in (403, 429):
            raise SavdoqRefused(response.status_code, _retry_after(response))
        if not 200 <= response.status_code < 300:
            raise SavdoqUnavailable(f'status {response.status_code}')
        return _parse_session(response.body)

    def revoke(self, subject_hash):
        response = self._send('DELETE', subject_hash, 'ru')
        if response.status_code != 204:
            raise SavdoqUnavailable(f'status {response.status_code}')

    def _send(self, method, subject_hash, language):
        configuration = self._configuration
        body = json.dumps({
            'publicKey': configuration.public_key,
            'origin': configuration.store_origin,
            'issuer': configuration.issuer,
            'subjectHash': subject_hash,
        }).encode('utf-8')
        try:
            with self._client.stream(
                method,
                f'{configuration.api_origin}{SESSIONS_PATH}',
                content=body,
                headers={
                    'Authorization': f'Bearer {configuration.service_token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'Accept-Language': language,
                },
            ) as response:
                return _BoundedResponse(
                    status_code=response.status_code,
                    retry_after=response.headers.get('Retry-After'),
                    body=_read_bounded(response),
                )
        except httpx.HTTPError:
            raise SavdoqUnavailable('transport failed') from None


@dataclass(frozen=True)
class _BoundedResponse:
    status_code: int
    retry_after: str | None
    body: bytes


def _read_bounded(response):
    chunks = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > MAXIMUM_RESPONSE_BYTES:
            raise SavdoqUnavailable('response too large')
        chunks.append(chunk)
    return b''.join(chunks)


def _retry_after(response):
    value = response.retry_after
    return int(value) if isinstance(value, str) and RETRY_AFTER_SECONDS.fullmatch(value) else None


def _parse_session(body):
    try:
        value = json.loads(body)
    except ValueError:
        raise SavdoqUnavailable('invalid JSON') from None
    if not isinstance(value, dict):
        raise SavdoqUnavailable('invalid session')
    token = value.get('accessToken')
    if (
        not isinstance(token, str) or not ACCESS_TOKEN.fullmatch(token)
        or value.get('tokenType') != 'Bearer'
        or value.get('shopperAuthenticated', True) is not True
    ):
        raise SavdoqUnavailable('invalid session')
    expires_at = _parse_expiry(value.get('expiresAt'))
    session_id = value.get('sessionId')
    if session_id is not None:
        try:
            session_id = uuid.UUID(session_id)
        except (TypeError, ValueError, AttributeError):
            raise SavdoqUnavailable('invalid session id') from None
    return IssuedSession(access_token=token, expires_at=expires_at, session_id=session_id)


def _parse_expiry(value):
    try:
        expires_at = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise SavdoqUnavailable('invalid expiry') from None
    if expires_at.tzinfo is None or expires_at <= timezone.now() + MINIMUM_REMAINING_LIFETIME:
        raise SavdoqUnavailable('invalid expiry')
    return expires_at
