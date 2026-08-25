from urllib.parse import urlparse

from django.conf import settings

from integration.errors import IntegrationProblem


LOCAL_DEVELOPMENT_HOSTNAMES = {
    'localhost',
    '127.0.0.1',
    '::1',
    'host.docker.internal',
    'gateway.docker.internal',
}


def https_origin(setting_name):
    value = getattr(settings, setting_name, '')
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        valid_port = parsed.port in {None, 443}
    except (TypeError, ValueError):
        raise _misconfigured_origin() from None
    if not hostname or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
        raise _misconfigured_origin()
    local_origin = (
        getattr(settings, 'DEBUG', False)
        and getattr(settings, 'SAVDOQ_ALLOW_LOCAL_ORIGINS', False)
        and parsed.scheme == 'http'
        and hostname.lower() in LOCAL_DEVELOPMENT_HOSTNAMES
        and parsed.port is not None
    )
    if parsed.scheme != 'https' and not local_origin:
        raise _misconfigured_origin()
    if not local_origin and not valid_port:
        raise _misconfigured_origin()
    return _origin(parsed, include_port=local_origin)


def cart_ttl_seconds():
    value = getattr(settings, 'SAVDOQ_CART_TTL_SECONDS', 3_600)
    if isinstance(value, bool) or not isinstance(value, int) or not 300 <= value <= 86_400:
        raise IntegrationProblem(503, 'Service unavailable', 'Integration cart TTL is misconfigured')
    return value


def _misconfigured_origin():
    return IntegrationProblem(503, 'Service unavailable', 'Integration origin is misconfigured')


def _origin(parsed, include_port=False):
    hostname = parsed.hostname
    if ':' in hostname:
        hostname = '[{}]'.format(hostname)
    port = ':{}'.format(parsed.port) if include_port and parsed.port is not None else ''
    return '{}://{}{}'.format(parsed.scheme, hostname, port)
