from django.test import TestCase
from rest_framework.test import APIClient

from nutrition.models import NutritionProfile
from store.models import Product


class NutritionApiTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name_ru='Курица с рисом', name_uz='Guruch bilan tovuq', slug='chicken-rice-test',
            description_ru='<p>Блюдо</p>', description_uz='<p>Taom</p>', price=65000,
            country_ru='Uzbekistan', country_uz='Uzbekistan', product_type=Product.TYPE_MEAL,
            quantity=12,
        )
        NutritionProfile.objects.create(
            product=self.product, portion_weight_grams=350, servings=1, calories_kcal=420,
            protein_grams=32, fat_grams=12, carbohydrate_grams=35,
            storage_ru='<p>Холодильник</p>', storage_uz='<p>Muzlatgich</p>',
            serving_ru='<p>Разогреть</p>', serving_uz='<p>Isiting</p>',
        )
        self.client = APIClient()

    def test_nutrition_catalog_exposes_canonical_profile(self):
        response = self.client.get('/api/v1/nutrition/', HTTP_ACCEPT_LANGUAGE='ru')
        self.assertEqual(response.status_code, 200)
        item = response.data['data'][0]
        self.assertEqual(item['product_type'], 'meal')
        self.assertEqual(item['nutrition_profile']['calories_kcal'], 420)
        self.assertNotIn('name_ru', item['nutrition_profile'])

    def test_quote_rechecks_live_product(self):
        response = self.client.post(
            '/api/v1/nutrition/checkout/quote/',
            {'baskets': [{'product': self.product.pk, 'quantity': 2}], 'type': 'dcb'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['subtotal'], 130000)

        self.product.quantity = 1
        self.product.save(update_fields=('quantity', 'updated_at'))
        unavailable = self.client.post(
            '/api/v1/nutrition/checkout/quote/',
            {'baskets': [{'product': self.product.pk, 'quantity': 2}], 'type': 'dcb'},
            format='json',
        )
        self.assertEqual(unavailable.status_code, 409)
