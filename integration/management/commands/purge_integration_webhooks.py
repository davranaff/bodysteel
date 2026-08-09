from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from integration.models import IntegrationWebhookEvent


class Command(BaseCommand):
    help = 'Delete terminal SAVDOQ webhook events after bounded retention windows.'

    def add_arguments(self, parser):
        parser.add_argument('--delivered-retention-days', type=int, default=30)
        parser.add_argument('--failed-retention-days', type=int, default=90)
        parser.add_argument('--batch-size', type=int, default=500)

    def handle(self, *args, **options):
        delivered_days = options['delivered_retention_days']
        failed_days = options['failed_retention_days']
        batch_size = options['batch_size']
        if not 1 <= delivered_days <= 365 or not 1 <= failed_days <= 730:
            raise CommandError('Webhook retention days are out of range')
        if failed_days < delivered_days:
            raise CommandError('Failed webhook retention must not be shorter than delivered retention')
        if not 1 <= batch_size <= 5_000:
            raise CommandError('batch-size must be between 1 and 5000')

        now = timezone.now()
        terminal = Q(
            status='delivered',
            delivered_at__lt=now - timedelta(days=delivered_days),
        ) | Q(
            status='failed',
            created_at__lt=now - timedelta(days=failed_days),
        )
        deleted = 0
        while True:
            event_ids = list(
                IntegrationWebhookEvent.objects.filter(terminal)
                .order_by('created_at')
                .values_list('event_id', flat=True)[:batch_size]
            )
            if not event_ids:
                break
            batch_deleted, _ = IntegrationWebhookEvent.objects.filter(event_id__in=event_ids).delete()
            deleted += batch_deleted
        self.stdout.write('Deleted {} terminal integration webhook events'.format(deleted))
