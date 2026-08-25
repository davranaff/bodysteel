from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings

from integration.configuration import LOCAL_DEVELOPMENT_HOSTNAMES


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
    local_http = (
        getattr(settings, 'DEBUG', False)
        and getattr(settings, 'SAVDOQ_ALLOW_LOCAL_ORIGINS', False)
        and parsed.scheme == 'http'
        and parsed.hostname
        and parsed.hostname.lower() in LOCAL_DEVELOPMENT_HOSTNAMES
        and parsed.port is not None
    )
    if (
        not 1 <= len(url) <= 2_048
        or (parsed.scheme != 'https' and not local_http)
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or (not valid_port and not local_http)
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
