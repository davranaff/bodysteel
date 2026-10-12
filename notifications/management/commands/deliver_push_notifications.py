from django.core.management.base import BaseCommand, CommandError

from notifications.configuration import PushNotConfigured
from notifications.services.delivery import deliver_pending


class Command(BaseCommand):
    help = 'Deliver a bounded batch of due push outbox rows; safe for concurrent workers.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 500:
            raise CommandError('Limit must be between 1 and 500')
        try:
            processed = deliver_pending(limit=options['limit'])
        except PushNotConfigured:
            raise CommandError('Push provider is not configured. No deliveries attempted.') from None
        self.stdout.write('Processed: {}'.format(processed))
