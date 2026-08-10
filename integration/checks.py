from django.conf import settings
from django.core.checks import Error, register

from integration.http.authentication import is_valid_integration_token
from integration.webhooks.configuration import (
    WebhookConfigurationError,
    require_webhook_configuration,
    webhook_is_enabled,
)


@register()
def integration_configuration_checks(app_configs, **kwargs):
    issues = []
    if (
        getattr(settings, 'SAVDOQ_INTEGRATION_CHECK_ENABLED', False)
        and not _credentials_are_ready()
    ):
        issues.append(_credentials_error())
    url_configured = bool(getattr(settings, 'SAVDOQ_WEBHOOK_URL', ''))
    secret_configured = bool(getattr(settings, 'SAVDOQ_WEBHOOK_SECRET', ''))
    if not url_configured and not secret_configured:
        return issues
    if not webhook_is_enabled():
        return [*issues, _configuration_error()]
    try:
        require_webhook_configuration()
    except WebhookConfigurationError:
        return [*issues, _configuration_error()]
    return issues


def _credentials_are_ready():
    credentials = getattr(settings, 'SAVDOQ_INTEGRATION_CREDENTIALS', ())
    if not isinstance(credentials, (tuple, list)) or len(credentials) != 2:
        return False
    tokens = []
    scopes = []
    for credential in credentials:
        if not isinstance(credential, dict):
            return False
        token = credential.get('token')
        granted = credential.get('scopes')
        if not is_valid_integration_token(token):
            return False
        if not isinstance(granted, (tuple, list)) or not all(
            isinstance(scope, str) for scope in granted
        ):
            return False
        if len(granted) != len(set(granted)):
            return False
        tokens.append(token)
        scopes.append(frozenset(granted))
    return (
        len(set(tokens)) == 2
        and frozenset({'products:read', 'inventory:read', 'carts:write'}) in scopes
        and frozenset({'products:read', 'inventory:read'}) in scopes
    )


def _credentials_error():
    return Error(
        'SAVDOQ integration requires distinct full and read-only credentials '
        'of at least 32 characters.',
        id='integration.E002',
    )


def _configuration_error():
    return Error(
        'SAVDOQ webhook settings must contain one safe HTTPS URL and a separate signing secret.',
        id='integration.E001',
    )
