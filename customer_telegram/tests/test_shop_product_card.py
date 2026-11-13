import io
import json
import random
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from PIL import Image

from customer_telegram.i18n import message
from customer_telegram.models import CustomerTelegramWidget
from customer_telegram.tests.base import TELEGRAM_SETTINGS
from customer_telegram.tests.shop_base import ShopFixtures
from store.models import Order, ProductImage
from telegram_widgets.html import MAXIMUM_COMPRESSED_BYTES, MAXIMUM_HTML_BYTES, compressed_size


DESCRIPTION = (
    '<p>Сывороточный протеин для набора <b>мышечной массы</b> и восстановления &amp; роста.</p>'
    '<ul><li>24 г белка на порцию</li><li>Полный аминокислотный профиль</li></ul>'
)


@override_settings(**TELEGRAM_SETTINGS)
class ProductCardTests(ShopFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=self.media)
        media.enable()
        self.addCleanup(media.disable)
        cache.clear()
        self.whey.description_ru = DESCRIPTION
        self.whey.save(update_fields=('description_ru',))

    def add_photo(self, product, noisy=False):
        image = Image.new('RGB', (600, 600), (255, 255, 255))
        if noisy:
            generator = random.Random(7)
            image.putdata([tuple(generator.randrange(256) for _ in range(3)) for _ in range(600 * 600)])
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        ProductImage.objects.create(product=product, photo=ContentFile(buffer.getvalue(), name='фото товара.png'))

    def open_card(self, product):
        self.send(message('ru', 'menu_catalog'))
        storefront = self.storefront()
        outcome, state = self.tap(storefront, 'p:{}'.format(product.pk))
        return storefront, outcome, state

    def card(self):
        return CustomerTelegramWidget.objects.filter(chat=self.chat, kind='product').latest('pk')

    def test_tapping_a_product_sends_a_card_with_photo_and_plain_description(self):
        self.add_photo(self.whey)
        storefront, outcome, state = self.open_card(self.whey)
        self.assertEqual(outcome, 'answered')
        self.assertIn('ниже', state['m'])
        storefront.refresh_from_db()
        self.assertEqual(storefront.screen, 'h')
        sent = self.api.widgets[-1]
        self.assertIn('data:image/webp;base64,', sent['html'])
        self.assertIn('Сывороточный протеин для набора мышечной массы и восстановления \\u0026 роста.', sent['html'])
        self.assertNotIn('<b>мышечной', sent['html'])
        self.assertIn('Сывороточный протеин 2 кг', sent['caption'])
        self.assertLessEqual(compressed_size(sent['html']), MAXIMUM_COMPRESSED_BYTES)
        self.assertLessEqual(len(sent['html'].encode()), MAXIMUM_HTML_BYTES)
        self.assertEqual(json.loads(sent['chat_data']), {'q': 0, 'n': 0})
        self.assertEqual(self.card().screen, 'p:{}'.format(self.whey.pk))

    def test_a_hard_to_compress_photo_shrinks_until_the_card_fits(self):
        self.add_photo(self.whey, noisy=True)
        self.open_card(self.whey)
        sent = self.api.widgets[-1]
        self.assertEqual(self.api.widgets[-1]['caption'][:5], 'Сывор')
        self.assertLessEqual(compressed_size(sent['html']), MAXIMUM_COMPRESSED_BYTES)

    def test_a_product_without_photo_still_gets_a_card(self):
        self.open_card(self.creatine)
        sent = self.api.widgets[-1]
        self.assertNotIn('data:image', sent['html'])
        self.assertIn('Креатин моногидрат', sent['html'])

    def test_card_buttons_change_the_cart_within_stock_and_open_the_cart(self):
        self.open_card(self.whey)
        card = self.card()
        for _ in range(3):
            _, state = self.tap(card, 'a')
        self.assertEqual(state, {'q': 3, 'n': 3})
        _, state = self.tap(card, 'a')
        self.assertEqual(state['q'], 3)
        self.assertIn('столько есть на складе', state['m'])
        _, state = self.tap(card, 'd')
        self.assertEqual(state['q'], 2)
        widgets_before = len(self.api.widgets)
        _, state = self.tap(card, 'k')
        self.assertIn('Корзина', state['m'])
        self.assertEqual(len(self.api.widgets), widgets_before + 1)
        self.assertEqual(self.storefront().screen, 'k')

    def test_card_refuses_storefront_requests_and_other_senders(self):
        self.open_card(self.whey)
        card = self.card()
        outcome, state = self.tap(card, 'c:1:0')
        self.assertEqual((outcome, state), ('denied', None))
        outcome, state = self.tap(card, 'a', sender=9999)
        self.assertEqual((outcome, state), ('denied', None))

    def test_a_product_that_left_the_storefront_is_not_sent(self):
        self.send(message('ru', 'menu_catalog'))
        widgets_before = len(self.api.widgets)
        _, state = self.tap(self.storefront(), 'p:{}'.format(self.hidden.pk))
        self.assertIn('больше нет в продаже', state['m'])
        self.assertEqual(len(self.api.widgets), widgets_before)


@override_settings(**TELEGRAM_SETTINGS)
class OrdersScreenTests(ShopFixtures, TestCase):
    def test_orders_screen_without_orders_says_so(self):
        self.send(message('ru', 'menu_catalog'))
        _, state = self.tap(self.storefront(), 'r')
        self.assertEqual(state['v'], 'r')
        self.assertIn('Заказов пока нет', state['m'])

    def test_orders_placed_in_this_chat_show_status_and_total(self):
        self.send(message('ru', 'menu_catalog'))
        storefront = self.storefront()
        order = Order.objects.create(
            total_price=300_000, type='pickup', full_name='Ali Valiev', phone='+998901234567', address='-',
            status='moderation', payment_status='paid',
        )
        CustomerTelegramWidget.objects.create(chat=self.chat, message_id=555, kind='order', order=order)
        _, state = self.tap(storefront, 'r')
        self.assertEqual(state['i'], [[str(order.order_code), 'Оплачен · Новый', 300_000, 'ok']])
        self.assert_fits(state)
