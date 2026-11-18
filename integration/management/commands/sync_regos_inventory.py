from django.core.management.base import BaseCommand, CommandError

from integration.regos.prices import price_preview, prices_follow_regos
from integration.regos.sync import RegosSyncError, fetch_inventory, sync_from_regos


class Command(BaseCommand):
    help = 'Synchronize BodySteel quantities (and prices, when REGOS_SYNC_PRICES is on) from REGOS Item/GetExt.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--preview-prices', action='store_true',
            help='List linked cards whose price differs from REGOS and change nothing.',
        )

    def handle(self, *args, **options):
        try:
            if options['preview_prices']:
                return self._preview(fetch_inventory())
            result = sync_from_regos()
        except RegosSyncError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(
            'REGOS sync complete: received={0.received} updated={0.updated} repriced={0.repriced} '
            'linked={0.linked} unmatched={0.unmatched} invalid={0.invalid}'.format(result)
        ))

    def _preview(self, records):
        rows = price_preview(records)
        self.stdout.write('id\tsite\tregos\tqty\tnote\tname')
        for product, price, note in rows:
            self.stdout.write('{}\t{}\t{}\t{}\t{}\t{}'.format(
                product.pk, product.price, price or 0, product.quantity, note or 'изменится', product.name_ru,
            ))
        changing = sum(1 for _, _, note in rows if not note)
        self.stdout.write('{} prices differ, {} would change; REGOS_SYNC_PRICES is {}'.format(
            len(rows), changing, 'on' if prices_follow_regos() else 'off',
        ))
