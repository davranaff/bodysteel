from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from integration.models import IntegrationCart


class Command(BaseCommand):
    help = 'Delete expired SAVDOQ integration carts after a bounded retention window.'

    def add_arguments(self, parser):
        parser.add_argument('--retention-hours', type=int, default=24)
        parser.add_argument('--batch-size', type=int, default=500)

    def handle(self, *args, **options):
        retention_hours = options['retention_hours']
        batch_size = options['batch_size']
        if not 1 <= retention_hours <= 24 * 30:
            raise CommandError('retention-hours must be between 1 and 720')
        if not 1 <= batch_size <= 5_000:
            raise CommandError('batch-size must be between 1 and 5000')

        cutoff = timezone.now() - timedelta(hours=retention_hours)
        deleted = 0
        while True:
            cart_ids = list(
                IntegrationCart.objects.filter(expires_at__lt=cutoff)
                .order_by('expires_at')
                .values_list('pk', flat=True)[:batch_size]
            )
            if not cart_ids:
                break
            batch_deleted, _ = IntegrationCart.objects.filter(pk__in=cart_ids).delete()
            deleted += batch_deleted
        self.stdout.write('Deleted {} expired integration carts'.format(deleted))
