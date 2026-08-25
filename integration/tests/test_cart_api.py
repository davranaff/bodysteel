import json
from datetime import timedelta
from urllib.parse import urlparse

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from integration.models import IntegrationCart
from integration.tests.fixtures import READ_TOKEN, IntegrationAPITestCase


class CartIntegrationAPITests(IntegrationAPITestCase):
    def test_idempotency_key_uses_the_documented_safe_ascii_boundary(self):
        payload = self.cart_payload(str(self.products[0].pk))
        for key in ('short-1', 'x' * 129, 'unsafe key', 'ключ-0001'):
            self.assertEqual(self.post_cart(key, payload).status_code, 422)

        accepted = self.post_cart('safe-key_01:.-', payload)
        self.assertEqual(accepted.status_code, 201)

    def test_exact_replay_returns_one_durable_cart_and_conflict_is_rejected(self):
        payload = self.cart_payload(str(self.products[0].pk))
        first = self.post_cart('cart-replay-0001', payload)
        replay = self.post_cart('cart-replay-0001', payload)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(first.json(), replay.json())
        self.assertEqual(IntegrationCart.objects.count(), 1)
        self.assertEqual(urlparse(first.json()['cartUrl']).netloc, 'bodysteel.uz')

        conflict = self.post_cart(
            'cart-replay-0001',
            self.cart_payload(str(self.products[0].pk), quantity=2),
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(IntegrationCart.objects.count(), 1)

    def test_read_only_scope_and_strict_body_validation(self):
        forbidden = self.post_cart(
            'cart-scope-0001',
            self.cart_payload(str(self.products[0].pk)),
            token=READ_TOKEN,
        )
        self.assertEqual(forbidden.status_code, 403)

        unknown = self.cart_payload(str(self.products[0].pk))
        unknown['internalUserId'] = 'private'
        self.assertEqual(self.post_cart('cart-invalid-0001', unknown).status_code, 422)
        self.assertEqual(
            self.post_cart('cart-invalid-0002', self.cart_payload(str(self.products[2].pk))).status_code,
            422,
        )
        malformed = self.client.generic(
            'POST',
            '/integration/v1/carts',
            data=b'{',
            content_type='application/json',
            headers={**self.auth_headers(), 'Idempotency-Key': 'cart-invalid-0003'},
        )
        self.assertEqual(malformed.status_code, 400)

        long_attribution = self.cart_payload(str(self.products[0].pk))
        long_attribution['attribution']['aiSessionId'] = 'x' * 201
        self.assertEqual(self.post_cart('cart-invalid-0004', long_attribution).status_code, 422)

    def test_restore_token_returns_frontend_cart_and_expires(self):
        response = self.post_cart(
            'cart-restore-0001',
            self.cart_payload(str(self.products[0].pk), quantity=2),
        )
        token = urlparse(response.json()['cartUrl']).fragment

        restored = self.restore_cart(token)
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored['Cache-Control'], 'no-store')
        self.assertEqual(restored.json()['items'][0]['count'], 2)
        self.assertEqual(restored.json()['items'][0]['product']['id'], self.products[0].pk)

        IntegrationCart.objects.filter(restore_token=token).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        expired = self.restore_cart(token)
        self.assertEqual(expired.status_code, 410)

    def test_expired_cart_retention_is_bounded(self):
        self.post_cart('cart-retention-0001', self.cart_payload(str(self.products[0].pk)))
        cart = IntegrationCart.objects.get()
        IntegrationCart.objects.filter(pk=cart.pk).update(
            expires_at=timezone.now() - timedelta(hours=25)
        )

        call_command('purge_expired_integration_carts', retention_hours=24, verbosity=0)

        self.assertFalse(IntegrationCart.objects.filter(pk=cart.pk).exists())

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=2)
    def test_request_body_memory_limit_returns_payload_too_large(self):
        response = self.post_cart(
            'cart-too-large-0001',
            self.cart_payload(str(self.products[0].pk)),
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()['title'], 'Payload too large')

    @override_settings(SAVDOQ_STOREFRONT_ORIGIN='https://bodysteel.uz:invalid')
    def test_malformed_storefront_origin_is_a_safe_service_error(self):
        response = self.post_cart(
            'cart-origin-0001',
            self.cart_payload(str(self.products[0].pk)),
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['detail'], 'Integration origin is misconfigured')

    def post_cart(self, idempotency_key, payload, token=None):
        headers = self.auth_headers(token=token) if token else self.auth_headers()
        headers['Idempotency-Key'] = idempotency_key
        return self.client.generic(
            'POST',
            '/integration/v1/carts',
            data=json.dumps(payload).encode('utf-8'),
            content_type='application/json',
            headers=headers,
        )

    def restore_cart(self, token):
        return self.client.generic(
            'POST',
            '/integration/v1/cart-restores',
            data=json.dumps({'token': token}).encode('utf-8'),
            content_type='application/json',
        )

    @staticmethod
    def cart_payload(product_id, quantity=1):
        return {
            'items': [{'productId': product_id, 'quantity': quantity}],
            'attribution': {'aiSessionId': 'ai-session-reference', 'channel': 'web'},
        }
