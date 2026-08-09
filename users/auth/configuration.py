from dataclasses import dataclass
from ipaddress import ip_network

from django.conf import settings

from users.auth.errors import configuration_problem


@dataclass(frozen=True)
class VerificationConfiguration:
    code_hash_key: bytes
    rate_hash_key: bytes
    ttl_seconds: int
    resend_seconds: int
    maximum_attempts: int


@dataclass(frozen=True)
class EskizConfiguration:
    email: str
    password: str
    sender: str
    template: str


def verification_configuration():
    try:
        code_key = _secret('PHONE_VERIFICATION_HASH_KEY')
        rate_key = _secret('AUTH_RATE_LIMIT_HASH_KEY')
        ttl = _integer('PHONE_VERIFICATION_TTL_SECONDS', 120, 900)
        resend = _integer('PHONE_VERIFICATION_RESEND_SECONDS', 30, 300)
        attempts = _integer('PHONE_VERIFICATION_MAX_ATTEMPTS', 3, 10)
    except (TypeError, ValueError):
        raise configuration_problem() from None
    if code_key == rate_key:
        raise configuration_problem()
    return VerificationConfiguration(code_key, rate_key, ttl, resend, attempts)


def storefront_proxy_token():
    try:
        return _secret('BODYSTEEL_STOREFRONT_PROXY_TOKEN').decode('utf-8')
    except (TypeError, ValueError, UnicodeDecodeError):
        raise configuration_problem() from None


def eskiz_configuration():
    if getattr(settings, 'SMS_BACKEND', 'disabled') != 'eskiz':
        raise configuration_problem()
    values = [
        getattr(settings, 'ESKIZ_PROVIDER_EMAIL', ''),
        getattr(settings, 'ESKIZ_PROVIDER_PASSWORD', ''),
        getattr(settings, 'ESKIZ_FROM_TO', ''),
        getattr(settings, 'ESKIZ_OTP_TEMPLATE', ''),
    ]
    if not all(isinstance(value, str) and value for value in values):
        raise configuration_problem()
    if values[0] != values[0].strip() or values[2] != values[2].strip():
        raise configuration_problem()
    template = values[3]
    if template.count('{code}') != 1 or '{' in template.replace('{code}', ''):
        raise configuration_problem()
    if len(template.replace('{code}', '000000')) > 500:
        raise configuration_problem()
    return EskizConfiguration(*values)


def trusted_proxy_networks():
    try:
        networks = tuple(
            ip_network(value, strict=False) for value in settings.AUTH_TRUSTED_PROXY_NETWORKS
        )
    except (AttributeError, TypeError, ValueError):
        raise configuration_problem() from None
    if any(network.prefixlen == 0 for network in networks):
        raise configuration_problem()
    return networks


def _secret(name):
    value = getattr(settings, name, '')
    if not isinstance(value, str) or len(value.encode('utf-8')) < 32:
        raise ValueError(name)
    return value.encode('utf-8')


def _integer(name, minimum, maximum):
    value = getattr(settings, name, '')
    if isinstance(value, bool):
        raise TypeError(name)
    parsed = int(value)
    if not minimum <= parsed <= maximum:
        raise ValueError(name)
    return parsed
