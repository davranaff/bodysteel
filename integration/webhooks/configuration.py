from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings


class WebhookConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class WebhookConfiguration:
    url: str
    secret: str


def webhook_is_enabled():
    return bool(
        getattr(settings, 'SAVDOQ_WEBHOOK_URL', '')
        and getattr(settings, 'SAVDOQ_WEBHOOK_SECRET', '')
    )


def require_webhook_configuration():
    url = getattr(settings, 'SAVDOQ_WEBHOOK_URL', '')
    secret = getattr(settings, 'SAVDOQ_WEBHOOK_SECRET', '')
    if not isinstance(url, str) or not isinstance(secret, str):
        raise WebhookConfigurationError('Webhook configuration is invalid')
    try:
        parsed = urlparse(url)
        valid_port = parsed.port in {None, 443}
    except ValueError:
        raise WebhookConfigurationError('Webhook configuration is invalid') from None
    if (
        not 1 <= len(url) <= 2_048
        or parsed.scheme != 'https'
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or not valid_port
        or not parsed.path.startswith('/')
        or parsed.query
        or parsed.fragment
    ):
        raise WebhookConfigurationError('Webhook configuration is invalid')
    if not 32 <= len(secret) <= 512 or secret.strip() != secret or _has_control(secret):
        raise WebhookConfigurationError('Webhook configuration is invalid')
    return WebhookConfiguration(url=url, secret=secret)


def _has_control(value):
    return any(ord(character) <= 31 or ord(character) == 127 for character in value)
