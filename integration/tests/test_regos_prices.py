from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import override_settings

from integration.regos.sync import apply_records, record_from_regos, sync_from_regos
from integration.tests.fixtures import IntegrationAPITestCase
from integration.tests.test_regos_inventory import REGOS_SETTINGS
from store.models import Product
from store.serializers.products import ProductSerializer


UZS = {'id': 1, 'name': 'Розничная цена', 'currency': {'code_chr': 'UZS'}}
FIXTURE_STOCK = {9001: 5, 9002: 2, 9003: 0}


def getext_row(item_id, price, quantity=None, price_type=UZS):
    return {
        'item': {'id': item_id, 'name': 'REGOS {}'.format(item_id)},
        'quantity': {'allowed': FIXTURE_STOCK[item_id] if quantity is None else quantity},
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


def item_event(*rows):
    return apply_records([record_from_regos(row) for row in rows], source='item-edited', update_catalog=True, follow_prices=True)


@override_settings(**REGOS_SETTINGS, REGOS_SYNC_PRICES=True)
class RegosPriceTests(IntegrationAPITestCase):
    def setUp(self):
        for index, product in enumerate(self.products):
            Product.objects.filter(pk=product.pk).update(regos_item_id=9001 + index, discounted_price=0)

    def card(self, index=0):
        return Product.objects.get(pk=self.products[index].pk)

    def test_the_first_sync_only_remembers_regos_prices(self):
        before = self.card()
        with regos_session(getext_row(9001, 215000.0)):
            result = sync_from_regos()
        card = self.card()
        self.assertEqual((result.repriced, card.price, card.regos_price), (0, 200_000, 215_000))
        self.assertEqual(card.updated_at, before.updated_at)

    def test_a_price_changed_in_regos_moves_the_site_price(self):
        Product.objects.filter(pk=self.products[0].pk).update(regos_price=215_000)
        with regos_session(getext_row(9001, 215000.0)):
            self.assertEqual(sync_from_regos().repriced, 0)
        with regos_session(getext_row(9001, 230000.0)):
            self.assertEqual(sync_from_regos().repriced, 1)
        self.assertEqual((self.card().price, self.card().regos_price), (230_000, 230_000))

    def test_an_item_edit_in_regos_brings_its_price(self):
        Product.objects.filter(pk=self.products[0].pk).update(regos_price=215_000)
        self.assertEqual(item_event(getext_row(9001, 215000.0)).repriced, 1)
        self.assertEqual(self.card().price, 215_000)

    def test_with_the_switch_off_only_regos_drafts_follow(self):
        Product.objects.filter(pk=self.products[0].pk).update(regos_price=215_000)
        Product.objects.filter(pk=self.products[1].pk).update(
            regos_price=215_000, regos_catalog_status=Product.REGOS_STATUS_DRAFT,
        )
        with override_settings(REGOS_SYNC_PRICES=False), \
                regos_session(getext_row(9001, 230000.0), getext_row(9002, 230000.0)):
            sync_from_regos()
        self.assertEqual((self.card(0).price, self.card(0).regos_price), (200_000, 230_000))
        self.assertEqual(self.card(1).price, 230_000)

    def test_discounted_archived_and_unpriced_cards_keep_their_price(self):
        Product.objects.filter(pk=self.products[0].pk).update(discounted_price=50_000, regos_price=100_000)
        Product.objects.filter(pk=self.products[1].pk).update(
            regos_catalog_status=Product.REGOS_STATUS_ARCHIVED, regos_price=100_000,
        )
        Product.objects.filter(pk=self.products[2].pk).update(regos_price=100_000)
        result = item_event(getext_row(9001, 150000.0), getext_row(9002, 150000.0), getext_row(9003, 0.0))
        self.assertEqual(result.repriced, 0)
        self.assertEqual([self.card(index).price for index in range(3)], [200_000, 200_000, 200_000])

    def test_a_price_type_in_another_currency_is_ignored(self):
        dollars = {'id': 2, 'name': 'USD', 'currency': {'code_chr': 'USD'}}
        item_event(getext_row(9001, 17.0, price_type=dollars))
        self.assertEqual((self.card().price, self.card().regos_price), (200_000, None))

    def test_to_server_export_never_touches_prices(self):
        result = apply_records([
            record_from_regos({'item': {'id': 9001, 'name': 'x', 'price': 99_000}, 'quantity': {'allowed': 1}}),
        ], source='REGOS To Server')
        self.assertEqual((result.repriced, self.card().price, self.card().regos_price), (0, 200_000, None))

    def test_a_draft_never_drops_below_its_discount(self):
        Product.objects.filter(pk=self.products[1].pk).update(
            regos_catalog_status=Product.REGOS_STATUS_DRAFT, discounted_price=50_000,
        )
        self.assertEqual(item_event(getext_row(9002, 30000.0)).repriced, 0)
        self.assertEqual(self.card(1).price, 200_000)

    def test_the_remembered_price_stays_out_of_the_storefront_card(self):
        self.assertNotIn('regos_price', ProductSerializer().fields)

    def test_preview_lists_differences_and_writes_nothing(self):
        Product.objects.filter(pk=self.products[1].pk).update(discounted_price=50_000)
        output = StringIO()
        with regos_session(getext_row(9001, 215000.0), getext_row(9002, 150000.0), getext_row(9003, 0.0)):
            call_command('sync_regos_inventory', '--preview-prices', stdout=output)
        text = output.getvalue()
        self.assertIn('200000\t215000\t5\tизменится при изменении в REGOS\tКреатин 1', text)
        self.assertIn('скидка на сайте, цена не меняется', text)
        self.assertIn('в REGOS нет цены', text)
        self.assertIn('3 prices differ, 1 follow REGOS on its next change', text)
        self.assertEqual([self.card(index).regos_price for index in range(3)], [None, None, None])
