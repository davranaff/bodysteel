from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError

from customer_telegram.bot_api import CustomerTelegramApi
from customer_telegram.configuration import require_configuration


class Command(BaseCommand):
    help = 'Run a read-only customer Telegram configuration and webhook preflight.'

    def handle(self, *args, **options):
        configuration = require_configuration()
        info = CustomerTelegramApi().get_webhook_info()
        if not info.ok or info.url != configuration.webhook_url:
            raise CommandError('Customer Telegram webhook does not match the configured endpoint.')
        if info.pending_update_count > 10_000:
            raise CommandError('Customer Telegram pending update count is too high.')
        parsed = urlsplit(info.url)
        self.stdout.write(self.style.SUCCESS(
            'Customer Telegram ready: {}{}, pending={}'.format(
                parsed.hostname, parsed.path, info.pending_update_count,
            ),
        ))
