from django.core.management.base import BaseCommand, CommandError

from integration.webhooks.configuration import WebhookConfigurationError
from integration.webhooks.delivery import WebhookDeliveryService
from integration.webhooks.transport import HttpxWebhookTransport


class Command(BaseCommand):
    help = 'Deliver a bounded batch of durable SAVDOQ webhook events.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 500:
            raise CommandError('limit must be between 1 and 500')
        transport = HttpxWebhookTransport()
        try:
            summary = WebhookDeliveryService(transport).deliver_batch(limit=limit)
        except WebhookConfigurationError:
            raise CommandError('SAVDOQ webhook delivery is not configured safely') from None
        finally:
            transport.close()
        self.stdout.write(
            'Webhook delivery: delivered={}, retried={}, failed={}'.format(
                summary.delivered,
                summary.retried,
                summary.failed,
            )
        )
        if summary.failed:
            raise CommandError('{} webhook event(s) permanently failed'.format(summary.failed))
