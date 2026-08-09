from django.core.checks import Error, register

from users.auth.configuration import (
    eskiz_configuration,
    storefront_proxy_token,
    trusted_proxy_networks,
    verification_configuration,
)
from users.auth.errors import AuthProblem


@register(deploy=True)
def auth_configuration_checks(app_configs, **kwargs):
    checks = (
        ('users.E001', storefront_proxy_token, 'Storefront proxy token is missing or too short.'),
        ('users.E002', verification_configuration, 'OTP hashing or lifetime settings are invalid.'),
        ('users.E003', eskiz_configuration, 'Eskiz OTP delivery settings are invalid.'),
        ('users.E004', trusted_proxy_networks, 'Trusted proxy networks are invalid.'),
    )
    errors = []
    for identifier, operation, message in checks:
        try:
            operation()
        except AuthProblem:
            errors.append(Error(message, id=identifier))
    return errors
