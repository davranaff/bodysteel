import time

from django.core.management.base import BaseCommand

from customer_telegram.campaigns import CampaignSummary, deliver_campaign_batch


class Command(BaseCommand):
    help = 'Deliver queued customer Telegram campaigns with bounded free-tier throughput.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 10_000:
            raise ValueError('limit must be between 1 and 10000')
        total = CampaignSummary()
        remaining = limit
        while remaining:
            batch_size = min(20, remaining)
            summary = deliver_campaign_batch(limit=batch_size)
            processed = sum((
                summary.delivered, summary.retried, summary.failed,
                summary.blocked, summary.skipped,
            ))
            for field in ('delivered', 'retried', 'failed', 'blocked', 'skipped'):
                setattr(total, field, getattr(total, field) + getattr(summary, field))
            remaining -= batch_size
            if processed < batch_size or remaining == 0:
                break
            time.sleep(1)
        self.stdout.write(
            'delivered={} retried={} failed={} blocked={} skipped={}'.format(
                total.delivered, total.retried, total.failed, total.blocked, total.skipped,
            ),
        )
