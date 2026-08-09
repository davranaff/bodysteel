from urllib.parse import urlparse

from django.conf import settings

from integration.errors import IntegrationProblem


def https_origin(setting_name):
    value = getattr(settings, setting_name, '')
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        valid_port = parsed.port in {None, 443}
    except (TypeError, ValueError):
        raise _misconfigured_origin() from None
    if (
        parsed.scheme != 'https'
        or not hostname
        or parsed.username
        or parsed.password
        or not valid_port
        or parsed.path not in {'', '/'}
        or parsed.query
        or parsed.fragment
    ):
        raise _misconfigured_origin()
    return 'https://{}'.format(hostname)


def cart_ttl_seconds():
    value = getattr(settings, 'SAVDOQ_CART_TTL_SECONDS', 3_600)
    if isinstance(value, bool) or not isinstance(value, int) or not 300 <= value <= 86_400:
        raise IntegrationProblem(503, 'Service unavailable', 'Integration cart TTL is misconfigured')
    return value


def _misconfigured_origin():
    return IntegrationProblem(503, 'Service unavailable', 'Integration origin is misconfigured')
