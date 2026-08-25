from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError

from customer_telegram.bot_api import CustomerTelegramApi, DeliveryStatus
from customer_telegram.configuration import require_configuration
from customer_telegram.i18n import commands


class Command(BaseCommand):
    help = 'Configure the isolated customer Telegram webhook and localized commands.'

    def handle(self, *args, **options):
        configuration = require_configuration()
        api = CustomerTelegramApi()
        result = api.set_webhook()
        if result.status is not DeliveryStatus.SENT:
            raise CommandError('Customer Telegram webhook configuration failed.')
        for language in ('ru', 'uz'):
            command_result = api.set_my_commands(commands(language), language)
            if command_result.status is not DeliveryStatus.SENT:
                raise CommandError('Customer Telegram command configuration failed.')
        parsed = urlsplit(configuration.webhook_url)
        self.stdout.write(self.style.SUCCESS(
            'Customer Telegram webhook configured for {}{}'.format(parsed.hostname, parsed.path),
        ))
