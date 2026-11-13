import json

from django.test import TestCase, override_settings

from customer_telegram.i18n import message
from customer_telegram.models import CustomerTelegramCart
from customer_telegram.tests.base import TELEGRAM_SETTINGS
from customer_telegram.tests.shop_base import CHAT_ID, ShopFixtures


@override_settings(**TELEGRAM_SETTINGS)
class StorefrontTests(ShopFixtures, TestCase):
    def test_catalog_button_sends_storefront_widget_with_visible_categories_only(self):
        self.assertEqual(self.send(message('ru', 'menu_catalog')), 'catalog')
        widget = self.api.widgets[-1]
        self.assertIn('Каталог BODYSTEEL', widget['caption'])
        self.assertIn('"c":[[{},"Протеин"]]'.format(self.category.pk), widget['html'])
        self.assertEqual(self.storefront().screen, 'h')

    def test_old_store_button_still_opens_the_catalog(self):
        self.assertEqual(self.send(message('ru', 'menu_store')), 'catalog')

    def test_category_list_hides_drafts_and_shows_discounted_price(self):
        self.send(message('ru', 'menu_catalog'))
        outcome, state = self.tap(self.storefront(), 'c:{}:0'.format(self.category.pk))
        self.assertEqual(outcome, 'answered')
        names = [row[1] for row in state['i']]
        self.assertNotIn('Черновик', names)
        whey = next(row for row in state['i'] if row[0] == self.whey.pk)
        self.assertEqual(whey[2:5], [400_000, 450_000, True])
        self.assert_fits(state)
        saved = self.api.edits[-1]
        self.assertEqual(saved[0], 'data')
        self.assertEqual(json.loads(saved[3]), state)

    def test_add_respects_stock_and_updates_cart_count(self):
        self.send(message('ru', 'menu_catalog'))
        widget = self.storefront()
        self.tap(widget, 'c:{}:0'.format(self.category.pk))
        for _ in range(3):
            _, state = self.tap(widget, 'a:{}'.format(self.whey.pk))
        whey = next(row for row in state['i'] if row[0] == self.whey.pk)
        self.assertEqual(whey[5], 3)
        self.assertEqual(state['n'], 3)
        _, state = self.tap(widget, 'a:{}'.format(self.whey.pk))
        self.assertIn('столько есть на складе', state['m'])
        _, state = self.tap(widget, 'd:{}'.format(self.whey.pk))
        whey = next(row for row in state['i'] if row[0] == self.whey.pk)
        self.assertEqual(whey[5], 2)

    def test_hidden_or_unknown_products_cannot_be_added(self):
        self.send(message('ru', 'menu_catalog'))
        _, state = self.tap(self.storefront(), 'a:{}'.format(self.hidden.pk))
        self.assertIn('больше нет в продаже', state['m'])
        self.assertFalse(CustomerTelegramCart.objects.filter(chat=self.chat, items__has_key=str(self.hidden.pk)).exists())

    def test_cart_screen_totals_lines(self):
        self.send(message('ru', 'menu_catalog'))
        widget = self.storefront()
        self.tap(widget, 'a:{}'.format(self.whey.pk))
        self.tap(widget, 'a:{}'.format(self.creatine.pk))
        self.tap(widget, 'a:{}'.format(self.creatine.pk))
        _, state = self.tap(widget, 'k')
        self.assertEqual(state['v'], 'k')
        self.assertEqual(state['s'], 400_000 + 2 * 150_000)
        self.assertEqual(state['n'], 3)

    def test_typed_text_is_a_search(self):
        self.assertEqual(self.send('креатин'), 'search')
        widget = self.storefront()
        self.assertEqual(widget.search_query, 'креатин')
        _, state = self.tap(widget, 's:0')
        self.assertEqual(state['i'][0][0], self.creatine.pk)

    def test_product_card_links_to_the_site(self):
        self.send(message('ru', 'menu_catalog'))
        self.tap(self.storefront(), 'p:{}'.format(self.whey.pk))
        self.assertIn('"u":"https://bodysteel.uz/product/whey"', self.api.widgets[-1]['html'])

    def test_another_user_or_unknown_message_is_denied(self):
        self.send(message('ru', 'menu_catalog'))
        outcome, state = self.tap(self.storefront(), 'h', sender=CHAT_ID + 1)
        self.assertEqual((outcome, state), ('denied', None))
        widget = self.storefront()
        widget.message_id += 500
        outcome, _ = self.tap(widget, 'h')
        self.assertEqual(outcome, 'denied')

    def test_malformed_request_data_is_denied(self):
        self.send(message('ru', 'menu_catalog'))
        for data in ('c:abc', 'a:1;drop', 'x' * 65, 't:express'):
            with self.subTest(data=data):
                self.assertEqual(self.tap(self.storefront(), data)[0], 'denied')

    def test_long_catalog_page_still_fits_1024_bytes(self):
        for index in range(12):
            self.product('Очень длинное название спортивного питания с вкусом шоколада номер {}'.format(index),
                         'long-{}'.format(index), price=999_999, discount=99_999)
        self.send(message('ru', 'menu_catalog'))
        _, state = self.tap(self.storefront(), 'c:{}:0'.format(self.category.pk))
        self.assertEqual(len(state['i']), 5)
        self.assertTrue(state['mo'])
        self.assert_fits(state)
