from django.core.checks import Error, register

from customer_telegram.configuration import (
    CustomerTelegramConfigurationError,
    customer_telegram_enabled,
    require_configuration,
)


@register(deploy=True)
def customer_telegram_configuration_check(app_configs, **kwargs):
    if not customer_telegram_enabled():
        return []
    try:
        require_configuration()
    except CustomerTelegramConfigurationError:
        return [Error(
            'Customer Telegram configuration is invalid.',
            id='customer_telegram.E001',
        )]
    return []
