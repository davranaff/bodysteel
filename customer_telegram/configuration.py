import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings


USERNAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]{3,30}[Bb][Oo][Tt]$')
BOT_TOKEN = re.compile(r'^\d{5,20}:[A-Za-z0-9_-]{30,128}$')
WEBHOOK_SECRET = re.compile(r'^[A-Za-z0-9_-]{32,256}$')
WEBHOOK_PATH = '/telegram/customer/webhook/'
UNSAFE_SECRET_MARKERS = (
    'change-me', 'changeme', 'unsafe', 'django-insecure', 'development', 'local-only',
)


class CustomerTelegramConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class CustomerTelegramConfiguration:
    token: str
    username: str
    webhook_secret: str
    link_hash_key: bytes
    public_origin: str
    webhook_url: str
    store_origin: str
    link_ttl_seconds: int
    contact_max_attempts: int
    campaigns_enabled: bool


def customer_telegram_enabled():
    return getattr(settings, 'CUSTOMER_TELEGRAM_ENABLED', False) is True


def require_configuration():
    if not customer_telegram_enabled():
        raise CustomerTelegramConfigurationError('Customer Telegram is disabled.')
    token = _nonempty('CUSTOMER_TELEGRAM_BOT_TOKEN')
    username = _nonempty('CUSTOMER_TELEGRAM_BOT_USERNAME')
    webhook_secret = _nonempty('CUSTOMER_TELEGRAM_WEBHOOK_SECRET')
    link_key = _secret('CUSTOMER_TELEGRAM_LINK_HASH_KEY')
    public_origin = _origin('CUSTOMER_TELEGRAM_PUBLIC_ORIGIN')
    webhook_url = _https_url('CUSTOMER_TELEGRAM_WEBHOOK_URL')
    store_origin = _origin('CUSTOMER_TELEGRAM_STORE_ORIGIN')
    ttl = _integer('CUSTOMER_TELEGRAM_LINK_TTL_SECONDS', 120, 900)
    attempts = _integer('CUSTOMER_TELEGRAM_CONTACT_MAX_ATTEMPTS', 1, 10)
    if not USERNAME.fullmatch(username):
        raise CustomerTelegramConfigurationError('Invalid bot username.')
    if not BOT_TOKEN.fullmatch(token):
        raise CustomerTelegramConfigurationError('Invalid bot token.')
    if not WEBHOOK_SECRET.fullmatch(webhook_secret):
        raise CustomerTelegramConfigurationError('Invalid webhook secret.')
    expected_webhook = '{}{}'.format(public_origin, WEBHOOK_PATH)
    if webhook_url != expected_webhook:
        raise CustomerTelegramConfigurationError('Invalid webhook URL.')
    if token == getattr(settings, 'BOT_TOKEN', ''):
        raise CustomerTelegramConfigurationError('Customer and staff bot tokens must differ.')
    secret_values = (
        link_key,
        webhook_secret.encode(),
        str(getattr(settings, 'SECRET_KEY', '')).encode(),
        str(getattr(settings, 'PHONE_VERIFICATION_HASH_KEY', '')).encode(),
        str(getattr(settings, 'AUTH_RATE_LIMIT_HASH_KEY', '')).encode(),
        str(getattr(settings, 'AUTH_CHALLENGE_HASH_KEY', '')).encode(),
        str(getattr(settings, 'BODYSTEEL_STOREFRONT_PROXY_TOKEN', '')).encode(),
    )
    populated = [value for value in secret_values if value]
    if len(populated) != len(set(populated)):
        raise CustomerTelegramConfigurationError('Customer Telegram secrets must be independent.')
    if not settings.DEBUG:
        protected = [token.encode(), *populated]
        if any(
            marker.encode() in value.lower()
            for value in protected
            for marker in UNSAFE_SECRET_MARKERS
        ):
            raise CustomerTelegramConfigurationError('Unsafe development secret is not allowed.')
    campaigns = getattr(settings, 'CUSTOMER_TELEGRAM_CAMPAIGNS_ENABLED', False) is True
    return CustomerTelegramConfiguration(
        token, username, webhook_secret, link_key, public_origin, webhook_url,
        store_origin, ttl, attempts, campaigns,
    )


def _nonempty(name):
    value = getattr(settings, name, '')
    if not isinstance(value, str) or not value or value != value.strip():
        raise CustomerTelegramConfigurationError('{} is invalid.'.format(name))
    return value


def _secret(name):
    value = _nonempty(name).encode('utf-8')
    if len(value) < 32:
        raise CustomerTelegramConfigurationError('{} is too short.'.format(name))
    return value


def _integer(name, minimum, maximum):
    value = getattr(settings, name, '')
    if isinstance(value, bool):
        raise CustomerTelegramConfigurationError('{} is invalid.'.format(name))
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise CustomerTelegramConfigurationError('{} is invalid.'.format(name)) from None
    if not minimum <= parsed <= maximum:
        raise CustomerTelegramConfigurationError('{} is invalid.'.format(name))
    return parsed


def _origin(name):
    value = _nonempty(name)
    parsed = urlsplit(value)
    if (
        parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
        or parsed.path or parsed.query or parsed.fragment or value.endswith('/')
    ):
        raise CustomerTelegramConfigurationError('{} is invalid.'.format(name))
    return value


def _https_url(name):
    value = _nonempty(name)
    parsed = urlsplit(value)
    if (
        parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
        or parsed.query or parsed.fragment
    ):
        raise CustomerTelegramConfigurationError('{} is invalid.'.format(name))
    return value
