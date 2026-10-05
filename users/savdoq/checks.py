from django.core.checks import Error, register

from users.savdoq.configuration import (
    SavdoqShopperConfigurationError,
    require_configuration,
    shopper_chat_configured,
)


@register(deploy=True)
def savdoq_shopper_configuration_check(app_configs, **kwargs):
    # Unconfigured is a valid "chat off" state; a partial setup is a mistake.
    if not shopper_chat_configured():
        return []
    try:
        require_configuration()
    except SavdoqShopperConfigurationError:
        return [Error(
            'SAVDOQ shopper chat configuration is invalid.',
            id='users.E101',
        )]
    return []
