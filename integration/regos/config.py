import re

from django.conf import settings


class RegosSyncError(Exception):
    """An expected configuration or upstream REGOS failure."""


_WHITESPACE = re.compile(r'\s+')


def endpoint():
    value = getattr(settings, 'REGOS_API_ENDPOINT', '').strip().rstrip('/')
    if not value:
        key = getattr(settings, 'REGOS_INTEGRATION_KEY', '').strip()
        if not key or '/' in key or any(character.isspace() for character in key):
            raise RegosSyncError('REGOS_INTEGRATION_KEY or REGOS_API_ENDPOINT must be configured')
        value = 'https://integration.regos.uz/gateway/out/{}/v1'.format(key)
    if not value.startswith('https://') or not value.endswith('/v1'):
        raise RegosSyncError('REGOS_API_ENDPOINT must be an HTTPS API v1 endpoint')
    return value


def timeout():
    value = getattr(settings, 'REGOS_API_TIMEOUT_SECONDS', 15)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 60:
        raise RegosSyncError('REGOS_API_TIMEOUT_SECONDS must be between 1 and 60')
    return value


def clean(value, length):
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return str(value).strip()[:length]
    return ''


def normalise(value):
    return _WHITESPACE.sub(' ', value).strip().casefold()
