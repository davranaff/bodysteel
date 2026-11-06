import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings


STORE_ID = re.compile(r'^(\d{1,12}|[0-9a-fA-F-]{36})$')
CODE = re.compile(r'^\d{1,20}$')
LOCAL_HOSTS = {'localhost', '127.0.0.1', '10.0.2.2'}


class MulticardNotConfigured(Exception):
    """Online payment is disabled or its server-only configuration is incomplete."""


@dataclass(frozen=True)
class MulticardConfiguration:
    base_url: str
    application_id: str
    secret: str
    store_id: str
    callback_url: str
    web_return_url: str
    app_return_url: str
    default_ikpu: str
    default_package_code: str
    delivery_ikpu: str
    delivery_package_code: str
    vat_percent: int | None
    tin: str
    invoice_ttl_seconds: int
    timeout_seconds: float

    def __repr__(self):
        # Never let the secret reach logs, tracebacks or debug pages.
        return 'MulticardConfiguration(base_url={!r}, store_id={!r})'.format(self.base_url, self.store_id)


def multicard_enabled():
    try:
        require_configuration()
    except MulticardNotConfigured:
        return False
    return True


def require_configuration():
    if not getattr(settings, 'MULTICARD_ENABLED', False):
        raise MulticardNotConfigured('disabled')
    base_url = _https_origin(settings.MULTICARD_BASE_URL)
    application_id = settings.MULTICARD_APPLICATION_ID
    secret = settings.MULTICARD_SECRET
    store_id = settings.MULTICARD_STORE_ID
    if not application_id or len(application_id) > 128 or not secret or len(secret) > 512:
        raise MulticardNotConfigured('credentials')
    if not STORE_ID.fullmatch(store_id or ''):
        raise MulticardNotConfigured('store_id')
    return MulticardConfiguration(
        base_url=base_url,
        application_id=application_id,
        secret=secret,
        store_id=store_id,
        callback_url=_url(settings.MULTICARD_CALLBACK_URL, allow_local=False),
        web_return_url=_url(settings.MULTICARD_WEB_RETURN_URL, allow_local=settings.DEBUG),
        app_return_url=_url(settings.MULTICARD_APP_RETURN_URL, allow_local=False),
        default_ikpu=_code(settings.MULTICARD_DEFAULT_IKPU),
        default_package_code=_code(settings.MULTICARD_DEFAULT_PACKAGE_CODE),
        delivery_ikpu=_code(settings.MULTICARD_DELIVERY_IKPU),
        delivery_package_code=_code(settings.MULTICARD_DELIVERY_PACKAGE_CODE),
        vat_percent=_optional_int(settings.MULTICARD_VAT_PERCENT, 0, 100),
        tin=_code(settings.MULTICARD_TIN),
        invoice_ttl_seconds=_bounded_int(settings.MULTICARD_INVOICE_TTL_SECONDS, 300, 86_400),
        timeout_seconds=float(_bounded_int(settings.MULTICARD_TIMEOUT_SECONDS, 2, 30)),
    )


def _https_origin(value):
    parts = urlsplit(value or '')
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise MulticardNotConfigured('base_url')
    if parts.path not in {'', '/'} or parts.query or parts.fragment:
        raise MulticardNotConfigured('base_url')
    return 'https://{}'.format(parts.netloc)


def _url(value, allow_local):
    parts = urlsplit(value or '')
    local = allow_local and parts.scheme == 'http' and parts.hostname in LOCAL_HOSTS
    if (parts.scheme != 'https' and not local) or not parts.hostname:
        raise MulticardNotConfigured('url')
    if parts.username or parts.password or parts.query or parts.fragment:
        raise MulticardNotConfigured('url')
    return value


def _code(value):
    if value and not CODE.fullmatch(value):
        raise MulticardNotConfigured('fiscal code')
    return value or ''


def _optional_int(value, minimum, maximum):
    return _bounded_int(value, minimum, maximum) if value not in (None, '') else None


def _bounded_int(value, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise MulticardNotConfigured('number') from None
    if not minimum <= number <= maximum:
        raise MulticardNotConfigured('number')
    return number
