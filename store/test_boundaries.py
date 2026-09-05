from types import SimpleNamespace

from django.test import SimpleTestCase

import store.models as public_models
from store.catalog.models import Product
from store.commerce.models import Basket, Order
from store.content.models import Menu


class StoreModelBoundaryTests(SimpleTestCase):
    def test_public_facade_keeps_existing_imports(self):
        self.assertIs(public_models.Product, Product)
        self.assertIs(public_models.Basket, Basket)
        self.assertIs(public_models.Order, Order)
        self.assertIs(public_models.Menu, Menu)

    def test_feature_modules_keep_original_tables(self):
        self.assertEqual(Product._meta.db_table, 'store_product')
        self.assertEqual(Basket._meta.db_table, 'store_basket')
        self.assertEqual(Menu._meta.db_table, 'store_menu')

    def test_historical_upload_callbacks_keep_module_path(self):
        callbacks = (
            public_models.blog_directory_path,
            public_models.brand_directory_path,
            public_models.category_directory_path,
            public_models.check_path,
            public_models.filial_image_directory_path,
            public_models.product_360_directory_path,
            public_models.product_image_directory_path,
        )
        self.assertTrue(all(callback.__module__ == 'store.models' for callback in callbacks))

    def test_product_upload_path_removes_invisible_and_path_characters(self):
        image = SimpleNamespace(
            product=SimpleNamespace(name_ru='Kevin Levrone 3 \u200b\u200bкг / шоколад'),
        )

        path = public_models.product_image_directory_path(
            image,
            'front\u200b/cover.webp',
        )

        self.assertEqual(
            path,
            'product_images/Kevin Levrone 3 кг шоколад/front cover.webp',
        )
        self.assertNotIn('\u200b', path)


class BasketDisplayTests(SimpleTestCase):
    def test_string_representation_is_finite_and_descriptive(self):
        basket = Basket(product_id=42, quantity=3)

        self.assertEqual(
            str(basket),
            'Корзина #new: товар 42, количество 3',
        )
