import base64
import io
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from PIL import Image

from customer_telegram.shop.thumbnails import PREFIX, product_thumbnail
from store.models import Product, ProductImage


class ProductThumbnailTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        settings = override_settings(MEDIA_ROOT=self.media)
        settings.enable()
        self.addCleanup(settings.disable)
        cache.clear()
        self.product = Product.objects.create(
            name_ru='Протеин с фото', name_uz='Rasmli protein', price=100_000, quantity=3,
            slug='photo-protein', country_ru='США', country_uz='AQSH',
        )

    def add_photo(self, mode='RGB', size=(800, 600), name='протеин 2 кг.png'):
        image = Image.new(mode, size, (200, 40, 40, 255) if mode == 'RGBA' else (200, 40, 40))
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        ProductImage.objects.create(product=self.product, photo=ContentFile(buffer.getvalue(), name=name))

    def test_photo_becomes_a_square_webp_data_url_within_the_budget(self):
        self.add_photo()
        uri = product_thumbnail(self.product, 700)
        self.assertTrue(uri.startswith(PREFIX))
        self.assertLessEqual(len(uri), 700)
        with Image.open(io.BytesIO(base64.b64decode(uri[len(PREFIX):]))) as decoded:
            self.assertEqual(decoded.format, 'WEBP')
            self.assertEqual(decoded.width, decoded.height)

    def test_transparent_photo_is_flattened_on_white(self):
        self.add_photo(mode='RGBA', size=(300, 500))
        uri = product_thumbnail(self.product, 900)
        with Image.open(io.BytesIO(base64.b64decode(uri[len(PREFIX):]))) as decoded:
            self.assertEqual(decoded.convert('RGB').getpixel((0, 0)), (255, 255, 255))

    def test_no_photo_tiny_budget_or_broken_file_means_no_thumbnail(self):
        self.assertIsNone(product_thumbnail(self.product, 900))
        self.add_photo()
        self.assertIsNone(product_thumbnail(self.product, 100))
        ProductImage.objects.filter(product=self.product).delete()
        ProductImage.objects.create(product=self.product, photo=ContentFile(b'not an image', name='broken.png'))
        with self.assertLogs('customer_telegram.shop.thumbnails', 'WARNING'):
            self.assertIsNone(product_thumbnail(self.product, 900))
