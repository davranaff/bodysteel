from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from customer_telegram.models import (
    CustomerTelegramCampaignRecipient,
    CustomerTelegramLink,
    CustomerTelegramUpdate,
)
from users.auth.models import AuthRateLimit


class Command(BaseCommand):
    help = 'Purge expired customer Telegram security and technical delivery records.'

    def add_arguments(self, parser):
        parser.add_argument('--link-retention-days', type=int, default=7)
        parser.add_argument('--update-retention-days', type=int, default=30)
        parser.add_argument('--delivery-retention-days', type=int, default=90)

    def handle(self, *args, **options):
        for name in ('link_retention_days', 'update_retention_days', 'delivery_retention_days'):
            if not 1 <= options[name] <= 3650:
                raise ValueError('{} must be between 1 and 3650'.format(name))
        now = timezone.now()
        links, _ = CustomerTelegramLink.objects.filter(
            expires_at__lt=now - timedelta(days=options['link_retention_days']),
        ).delete()
        updates, _ = CustomerTelegramUpdate.objects.filter(
            created_at__lt=now - timedelta(days=options['update_retention_days']),
        ).delete()
        deliveries, _ = CustomerTelegramCampaignRecipient.objects.filter(
            campaign__completed_at__lt=now - timedelta(days=options['delivery_retention_days']),
            status__in=('failed', 'skipped', 'blocked'),
        ).delete()
        security, _ = AuthRateLimit.objects.filter(
            scope__startswith='customer_telegram_', expires_at__lt=now,
        ).delete()
        self.stdout.write('links={} updates={} deliveries={} security={}'.format(
            links, updates, deliveries, security,
        ))
