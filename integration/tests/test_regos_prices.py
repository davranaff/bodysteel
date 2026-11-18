from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import override_settings

from integration.regos.sync import apply_records, record_from_regos, sync_from_regos
from integration.tests.fixtures import IntegrationAPITestCase
from integration.tests.test_regos_inventory import REGOS_SETTINGS
from store.models import Product


UZS = {'id': 1, 'name': 'Розничная цена', 'currency': {'code_chr': 'UZS'}}


def getext_row(item_id, price, quantity=4, price_type=UZS):
    return {
        'item': {'id': item_id, 'code': item_id, 'name': 'REGOS {}'.format(item_id)},
        'quantity': {'common': quantity, 'allowed': quantity},
        'price': price,
        'pricetype': price_type,
    }


def regos_session(*rows):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {'ok': True, 'result': list(rows), 'next_offset': len(rows), 'total': len(rows)}
    session = Mock()
    session.post.return_value = response
    return patch('integration.regos.sync.requests.Session', return_value=session)


@override_settings(**REGOS_SETTINGS)
class RegosPriceTests(IntegrationAPITestCase):
    def setUp(self):
        for index, product in enumerate(self.products):
            Product.objects.filter(pk=product.pk).update(regos_item_id=9001 + index, discounted_price=0)

    def price(self, index):
        return Product.objects.values_list('price', flat=True).get(pk=self.products[index].pk)

    def test_full_sync_moves_prices_only_when_switched_on(self):
        with regos_session(getext_row(9001, 215000.0)):
            result = sync_from_regos()
        self.assertEqual((result.repriced, self.price(0)), (0, 200_000))
        self.assertEqual(Product.objects.get(pk=self.products[0].pk).quantity, 4)

        with override_settings(REGOS_SYNC_PRICES=True), regos_session(getext_row(9001, 215000.0)):
            result = sync_from_regos()
        self.assertEqual((result.repriced, self.price(0)), (1, 215_000))

    @override_settings(REGOS_SYNC_PRICES=True)
    def test_discounted_archived_and_unpriced_cards_keep_their_price(self):
        Product.objects.filter(pk=self.products[0].pk).update(discounted_price=50_000)
        Product.objects.filter(pk=self.products[1].pk).update(regos_catalog_status=Product.REGOS_STATUS_ARCHIVED)
        with regos_session(getext_row(9001, 150000.0), getext_row(9002, 150000.0), getext_row(9003, 0.0)):
            result = sync_from_regos()
        self.assertEqual(result.repriced, 0)
        self.assertEqual([self.price(index) for index in range(3)], [200_000, 200_000, 200_000])

    @override_settings(REGOS_SYNC_PRICES=True)
    def test_a_price_type_in_another_currency_is_ignored(self):
        dollars = {'id': 2, 'name': 'USD', 'currency': {'code_chr': 'USD'}}
        with regos_session(getext_row(9001, 17.0, price_type=dollars)):
            sync_from_regos()
        self.assertEqual(self.price(0), 200_000)

    @override_settings(REGOS_SYNC_PRICES=True)
    def test_to_server_export_never_changes_prices(self):
        result = apply_records([
            record_from_regos({'item': {'id': 9001, 'name': 'x', 'price': 99_000}, 'quantity': {'allowed': 1}}),
        ], source='REGOS To Server')
        self.assertEqual((result.repriced, self.price(0)), (0, 200_000))

    def test_item_edit_follows_a_draft_but_never_drops_below_its_discount(self):
        Product.objects.filter(pk=self.products[0].pk).update(regos_catalog_status=Product.REGOS_STATUS_DRAFT)
        Product.objects.filter(pk=self.products[1].pk).update(
            regos_catalog_status=Product.REGOS_STATUS_DRAFT, discounted_price=50_000,
        )
        records = [record_from_regos(getext_row(9001, 230000.0)), record_from_regos(getext_row(9002, 30000.0))]
        result = apply_records(records, source='item-edited', update_catalog=True, follow_prices=True)
        self.assertEqual((result.repriced, self.price(0), self.price(1)), (1, 230_000, 200_000))

    def test_preview_lists_differences_and_writes_nothing(self):
        Product.objects.filter(pk=self.products[1].pk).update(discounted_price=50_000)
        output = StringIO()
        with regos_session(getext_row(9001, 215000.0, quantity=1), getext_row(9002, 150000.0), getext_row(9003, 0.0)):
            call_command('sync_regos_inventory', '--preview-prices', stdout=output)
        text = output.getvalue()
        self.assertIn('200000\t215000\t5\tизменится\tКреатин 1', text)
        self.assertIn('скидка на сайте, цена не меняется', text)
        self.assertIn('в REGOS нет цены', text)
        self.assertIn('3 prices differ, 1 would change; REGOS_SYNC_PRICES is off', text)
        self.assertEqual([self.price(index) for index in range(3)], [200_000, 200_000, 200_000])
        self.assertEqual(Product.objects.get(pk=self.products[0].pk).quantity, 5)
