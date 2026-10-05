import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings


SECRET = re.compile(r'^[A-Za-z0-9_-]{32,256}$')
PUBLIC_KEY = re.compile(r'^wpk_[A-Za-z0-9_-]{32}$')
SETTING_NAMES = (
    'SAVDOQ_API_ORIGIN',
    'SAVDOQ_WIDGET_PUBLIC_KEY',
    'SAVDOQ_SHOPPER_SERVICE_TOKEN',
    'SAVDOQ_SHOPPER_IDENTITY_KEY',
)
# Shopper identities are namespaced so SAVDOQ never sees a raw customer id.
ISSUER = 'bodysteel'


class SavdoqShopperConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class SavdoqShopperConfiguration:
    api_origin: str
    store_origin: str
    public_key: str
    service_token: str
    identity_key: bytes
    issuer: str = ISSUER


def shopper_chat_configured():
    return any(getattr(settings, name, '') for name in SETTING_NAMES)


def require_configuration():
    """Server-only SAVDOQ shopper-session credentials; never serialized to clients."""
    api_origin = _https_origin(getattr(settings, 'SAVDOQ_API_ORIGIN', ''))
    store_origin = _https_origin(getattr(settings, 'SAVDOQ_STOREFRONT_ORIGIN', ''))
    public_key = getattr(settings, 'SAVDOQ_WIDGET_PUBLIC_KEY', '')
    service_token = getattr(settings, 'SAVDOQ_SHOPPER_SERVICE_TOKEN', '')
    identity_key = getattr(settings, 'SAVDOQ_SHOPPER_IDENTITY_KEY', '')
    if not isinstance(public_key, str) or not PUBLIC_KEY.fullmatch(public_key):
        raise SavdoqShopperConfigurationError('Invalid SAVDOQ widget public key.')
    for value in (service_token, identity_key):
        if not isinstance(value, str) or not SECRET.fullmatch(value):
            raise SavdoqShopperConfigurationError('Invalid SAVDOQ shopper secret.')
    if service_token == identity_key:
        raise SavdoqShopperConfigurationError('SAVDOQ shopper secrets must be independent.')
    return SavdoqShopperConfiguration(
        api_origin=api_origin,
        store_origin=store_origin,
        public_key=public_key,
        service_token=service_token,
        identity_key=identity_key.encode('utf-8'),
    )


def _https_origin(value):
    if not isinstance(value, str) or not value:
        raise SavdoqShopperConfigurationError('Missing SAVDOQ origin.')
    parts = urlsplit(value)
    origin = f'{parts.scheme}://{parts.netloc}'
    if (
        parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
        or value != origin
    ):
        raise SavdoqShopperConfigurationError('SAVDOQ origins must be exact HTTPS origins.')
    return origin
