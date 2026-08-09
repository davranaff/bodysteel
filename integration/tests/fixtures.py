from datetime import datetime, timezone

from django.test import TestCase, override_settings

from store.models import Brand, Category, Product, ProductImage


FULL_TOKEN = 'full-integration-token-00000000000001'
READ_TOKEN = 'read-integration-token-00000000000001'
INTEGRATION_SETTINGS = {
    'SAVDOQ_INTEGRATION_CREDENTIALS': (
        {
            'token': FULL_TOKEN,
            'scopes': ('products:read', 'inventory:read', 'carts:write'),
        },
        {
            'token': READ_TOKEN,
            'scopes': ('products:read', 'inventory:read'),
        },
    ),
    'SAVDOQ_STOREFRONT_ORIGIN': 'https://bodysteel.uz',
    'SAVDOQ_MEDIA_ORIGIN': 'https://api.bodysteel.uz',
    'SAVDOQ_CART_TTL_SECONDS': 3_600,
}

WEBHOOK_SETTINGS = {
    'SAVDOQ_WEBHOOK_URL': 'https://savdoq.example.test/api/v1/webhooks/connections/connection-id',
    'SAVDOQ_WEBHOOK_SECRET': 'body-steel-webhook-secret-0000000000000001',
}


@override_settings(**INTEGRATION_SETTINGS)
class IntegrationAPITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(
            name_ru='Добавки',
            name_uz='Qo‘shimchalar',
            photo='categories/supplements.webp',
            slug='supplements',
            description='Category',
            sort=1,
        )
        brand = Brand.objects.create(name='BodySteel Test', photo='brand/test.webp')
        cls.products = [
            cls._product('Креатин 1', 'Kreatin 1', 'creatine-1', 5, brand, category),
            cls._product('Креатин 2', 'Kreatin 2', 'creatine-2', 2, brand, category),
            cls._product('Протеин 1', 'Protein 1', 'protein-1', 0, brand, category),
        ]
        timestamps = (
            '2026-08-08T00:00:00+00:00',
            '2026-08-08T00:30:00+00:00',
            '2026-08-08T00:45:00+00:00',
        )
        for product, timestamp in zip(cls.products, timestamps):
            Product.objects.filter(pk=product.pk).update(updated_at=datetime.fromisoformat(timestamp))
            product.refresh_from_db()

    @classmethod
    def _product(cls, name_ru, name_uz, slug, quantity, brand, category):
        product = Product.objects.create(
            name_ru=name_ru,
            name_uz=name_uz,
            description_ru='<p>Описание</p>',
            description_uz='<p>Tavsif</p>',
            price=200_000,
            discounted_price=10_000,
            quantity=quantity,
            slug=slug,
            country_ru='Узбекистан',
            country_uz='O‘zbekiston',
            composition_ru='<b>Состав</b>',
            composition_uz='<b>Tarkibi</b>',
            brand=brand,
        )
        product.category.add(category)
        ProductImage.objects.create(product=product, photo='product_images/{}.webp'.format(slug))
        return product

    def auth_headers(self, token=FULL_TOKEN, language='ru'):
        return {
            'Authorization': 'Bearer {}'.format(token),
            'Accept-Language': language,
        }

    @staticmethod
    def iso_timestamp(value):
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
