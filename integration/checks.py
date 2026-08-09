from django.conf import settings
from django.core.checks import Error, register

from integration.webhooks.configuration import (
    WebhookConfigurationError,
    require_webhook_configuration,
    webhook_is_enabled,
)


@register()
def integration_configuration_checks(app_configs, **kwargs):
    url_configured = bool(getattr(settings, 'SAVDOQ_WEBHOOK_URL', ''))
    secret_configured = bool(getattr(settings, 'SAVDOQ_WEBHOOK_SECRET', ''))
    if not url_configured and not secret_configured:
        return []
    if not webhook_is_enabled():
        return [_configuration_error()]
    try:
        require_webhook_configuration()
    except WebhookConfigurationError:
        return [_configuration_error()]
    return []


def _configuration_error():
    return Error(
        'SAVDOQ webhook settings must contain one safe HTTPS URL and a separate signing secret.',
        id='integration.E001',
    )
