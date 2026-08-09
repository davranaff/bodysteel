import json
from datetime import timedelta
from urllib.parse import urlparse

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from integration.models import (
    IntegrationCart,
    IntegrationOrderAttribution,
    IntegrationWebhookEvent,
)
from integration.tests.fixtures import IntegrationAPITestCase, WEBHOOK_SETTINGS
from store.models import Order


@override_settings(**WEBHOOK_SETTINGS)
class WebhookEventTests(IntegrationAPITestCase):
    def setUp(self):
        IntegrationWebhookEvent.objects.all().delete()

    def test_product_inventory_and_deletion_events_are_durable(self):
        product = self.products[0]
        product.quantity -= 1
        product.save(update_fields=('quantity', 'updated_at'))

        events = self.events()
        self.assertEqual(
            {event['type'] for event in events},
            {'product.updated', 'inventory.updated'},
        )
        self.assertTrue(all(event['apiVersion'] == '2026-08-01' for event in events))
        self.assertTrue(all(event['id'].startswith('event_') for event in events))

        IntegrationWebhookEvent.objects.all().delete()
        product_id = str(product.pk)
        product.delete()

        deleted = [event for event in self.events() if event['type'] == 'product.deleted']
        self.assertEqual(len(deleted), 1)
        self.assertEqual(deleted[0]['data'], {'productId': product_id})

    def test_ai_cart_is_attached_and_completed_order_event_contains_no_pii(self):
        cart = self.create_cart(
            'order-attribution-0001',
            self.cart_payload(str(self.products[0].pk), quantity=2),
        )
        token = urlparse(cart.json()['cartUrl']).fragment
        initial_quantity = self.products[0].quantity

        response = self.client.post(
            '/api/v1/users/orders/',
            data=json.dumps(self.order_payload(self.products[0].pk, token)),
            content_type='application/json',
            headers={'Idempotency-Key': 'attributed-order-0001'},
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.json()['orderId'])
        self.assertEqual(order.status, 'moderation')
        self.assertTrue(IntegrationOrderAttribution.objects.filter(order=order).exists())
        self.products[0].refresh_from_db()
        self.assertEqual(self.products[0].quantity, initial_quantity - 2)

        attribution = IntegrationOrderAttribution.objects.get(order=order)
        IntegrationCart.objects.filter(pk=attribution.cart_id).update(
            expires_at=timezone.now() - timedelta(hours=25)
        )
        call_command('purge_expired_integration_carts', retention_hours=24, verbosity=0)
        attribution.refresh_from_db()
        self.assertIsNone(attribution.cart_id)

        IntegrationWebhookEvent.objects.all().delete()
        original_code = order.order_code
        original_total = order.total_price
        order.status = 'purchased'
        order.save()
        order.refresh_from_db()

        self.assertEqual(order.order_code, original_code)
        self.assertEqual(order.total_price, original_total)
        event = json.loads(IntegrationWebhookEvent.objects.get().body)
        self.assertEqual(event['type'], 'order.completed')
        self.assertEqual(event['data']['orderId'], str(order.pk))
        self.assertEqual(event['data']['productIds'], [str(self.products[0].pk)])
        self.assertEqual(event['data']['channel'], 'web')
        self.assertEqual(event['data']['aiSessionId'], 'ai-session-reference')
        self.assertFalse({'full_name', 'phone', 'address'} & set(event['data']))

        order.save()
        self.assertEqual(IntegrationWebhookEvent.objects.count(), 1)

    def test_order_boundary_rejects_unknown_fields_and_stock_conflicts(self):
        payload = self.order_payload(self.products[0].pk)
        payload['status'] = 'purchased'
        self.assertEqual(
            self.post_order(payload).status_code,
            400,
        )

        unavailable = self.order_payload(self.products[1].pk)
        unavailable['baskets'][0]['quantity'] = self.products[1].quantity + 1
        response = self.post_order(unavailable)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Order.objects.count(), 0)

    @staticmethod
    def order_payload(product_id, token=None):
        return {
            'full_name': 'Test Customer',
            'phone': '+998 (90) 123-45-67',
            'address': '-',
            'type': 'pickup',
            'baskets': [{'product': product_id, 'quantity': 2}],
            'coupon_code': None,
            **({'integration_cart_token': token} if token else {}),
        }

    def post_order(self, payload, idempotency_key='order-boundary-0001'):
        return self.client.post(
            '/api/v1/users/orders/',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Idempotency-Key': idempotency_key},
        )

    def create_cart(self, idempotency_key, payload):
        return self.client.generic(
            'POST',
            '/integration/v1/carts',
            data=json.dumps(payload).encode('utf-8'),
            content_type='application/json',
            headers={
                **self.auth_headers(),
                'Idempotency-Key': idempotency_key,
            },
        )

    @staticmethod
    def cart_payload(product_id, quantity=1):
        return {
            'items': [{'productId': product_id, 'quantity': quantity}],
            'attribution': {'aiSessionId': 'ai-session-reference', 'channel': 'web'},
        }

    @staticmethod
    def events():
        return [
            json.loads(body)
            for body in IntegrationWebhookEvent.objects.order_by('created_at').values_list('body', flat=True)
        ]
