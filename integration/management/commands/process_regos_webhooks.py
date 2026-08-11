from django.core.management.base import BaseCommand

from integration.regos.queue import process_pending_events


class Command(BaseCommand):
    help = 'Process queued REGOS local-integration webhooks with retry backoff.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20)

    def handle(self, *args, **options):
        processed, retried = process_pending_events(limit=max(1, options['limit']))
        self.stdout.write('processed={} retried={}'.format(processed, retried))
