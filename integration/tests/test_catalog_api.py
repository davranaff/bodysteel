from datetime import timedelta

from store.models import Product, ProductImage

from integration.tests.fixtures import FULL_TOKEN, IntegrationAPITestCase


class CatalogIntegrationAPITests(IntegrationAPITestCase):
    def test_authentication_scopes_and_problem_details(self):
        missing = self.client.get('/integration/v1/products', headers={'Accept-Language': 'ru'})
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing['Content-Type'], 'application/problem+json')
        self.assertIn('Bearer', missing['WWW-Authenticate'])
        self.assertNotIn(FULL_TOKEN, missing.content.decode())

        invalid = self.client.get(
            '/integration/v1/products',
            headers=self.auth_headers(token='invalid-integration-token-00000001'),
        )
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.json()['status'], 401)

    def test_localized_cursor_pages_and_conditional_requests(self):
        first = self.client.get(
            '/integration/v1/products?limit=2',
            headers=self.auth_headers(language='en;q=0.1, uz-UZ;q=0.9'),
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first['Content-Language'], 'uz')
        self.assertIn('Accept-Language', [value.strip() for value in first['Vary'].split(',')])
        page = first.json()
        self.assertEqual([item['name'] for item in page['items']], ['Kreatin 1', 'Kreatin 2'])
        self.assertNotIn('name_uz', page['items'][0])
        self.assertTrue(page['hasMore'])

        etag = first['ETag']
        replay = self.client.get(
            '/integration/v1/products?limit=2',
            headers={**self.auth_headers(language='uz'), 'If-None-Match': etag},
        )
        self.assertEqual(replay.status_code, 304)
        self.assertEqual(replay.content, b'')
        self.assertEqual(replay['ETag'], etag)

        second = self.client.get(
            '/integration/v1/products',
            {'limit': 2, 'cursor': page['nextCursor']},
            headers=self.auth_headers(language='uz'),
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual([item['id'] for item in second.json()['items']], [str(self.products[2].pk)])
        self.assertFalse(second.json()['hasMore'])

        russian = self.client.get(
            '/integration/v1/products?limit=2',
            headers=self.auth_headers(language='ru'),
        )
        self.assertNotEqual(russian['ETag'], etag)

    def test_product_identity_delta_and_validation(self):
        product_id = str(self.products[0].pk)
        ru = self.client.get(
            '/integration/v1/products/{}'.format(product_id),
            headers=self.auth_headers(language='ru'),
        )
        uz = self.client.get(
            '/integration/v1/products/{}'.format(product_id),
            headers=self.auth_headers(language='uz'),
        )
        self.assertEqual(ru.json()['id'], uz.json()['id'])
        self.assertEqual(ru.json()['name'], 'Креатин 1')
        self.assertEqual(uz.json()['name'], 'Kreatin 1')
        self.assertNotIn('<p>', ru.json()['description'])

        delta = self.client.get(
            '/integration/v1/products',
            {'updatedAfter': '2026-08-08T00:00:00Z'},
            headers=self.auth_headers(),
        )
        self.assertEqual(
            [item['id'] for item in delta.json()['items']],
            [str(self.products[1].pk), str(self.products[2].pk)],
        )
        self.assertTrue(
            all(
                self.iso_timestamp(item['updatedAt']) > self.iso_timestamp('2026-08-08T00:00:00Z')
                for item in delta.json()['items']
            )
        )

        invalid_cursor = self.client.get(
            '/integration/v1/products?cursor=tampered',
            headers=self.auth_headers(),
        )
        self.assertEqual(invalid_cursor.status_code, 422)
        unsupported = self.client.get(
            '/integration/v1/products',
            headers=self.auth_headers(language='en'),
        )
        self.assertEqual(unsupported.status_code, 406)
        unknown_query = self.client.get(
            '/integration/v1/products?internal=true',
            headers=self.auth_headers(),
        )
        self.assertEqual(unknown_query.status_code, 422)

        missing = self.client.get(
            '/integration/v1/products/999999999',
            headers=self.auth_headers(),
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()['title'], 'Product not found')

    def test_inventory_is_live_bounded_and_deduplicated(self):
        product_id = str(self.products[0].pk)
        response = self.client.get(
            '/integration/v1/inventory',
            {'ids': '{},{},unknown'.format(product_id, product_id)},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['items'],
            [{'productId': product_id, 'stock': {'status': 'in_stock', 'quantity': 5}}],
        )

        too_many = ','.join('product-{}'.format(index) for index in range(101))
        rejected = self.client.get(
            '/integration/v1/inventory',
            {'ids': too_many},
            headers=self.auth_headers(),
        )
        self.assertEqual(rejected.status_code, 422)

    def test_related_catalog_changes_advance_product_watermark(self):
        product = self.products[0]
        Product.objects.filter(pk=product.pk).update(updated_at=product.updated_at - timedelta(days=1))
        product.refresh_from_db()
        previous = product.updated_at

        category = product.category.get()
        category.name_ru = 'Обновлённая категория'
        category.save()
        product.refresh_from_db()

        self.assertGreater(product.updated_at, previous)

    def test_moving_an_image_advances_both_product_watermarks(self):
        first, second = self.products[:2]
        previous = first.updated_at - timedelta(days=1)
        Product.objects.filter(pk__in=(first.pk, second.pk)).update(updated_at=previous)

        image = ProductImage.objects.get(product=first)
        image.product = second
        image.save()
        first.refresh_from_db()
        second.refresh_from_db()

        self.assertGreater(first.updated_at, previous)
        self.assertGreater(second.updated_at, previous)
