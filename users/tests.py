from django.test import TestCase

from store.models import Product
from users.serializers.basket import CreateBasketsListSerializer


class RegosManagedStockTests(TestCase):
    def test_legacy_basket_creation_keeps_product_quantity_unchanged(self):
        product = Product.objects.create(
            name_ru='Товар REGOS',
            name_uz='REGOS mahsuloti',
            price=100_000,
            quantity=7,
            slug='regos-managed-stock',
            country_ru='Узбекистан',
            country_uz='O‘zbekiston',
        )

        result = CreateBasketsListSerializer().create({
            'baskets': [{'product': product.pk, 'quantity': 2}],
        })

        product.refresh_from_db()
        self.assertEqual(product.quantity, 7)
        self.assertEqual(len(result['data']), 1)
