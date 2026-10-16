import hashlib
import json
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.authtoken.models import Token

from store.models import Order, Product
from users.models import User
from users.orders.idempotency import idempotency_digest, legacy_request_fingerprint


BUKHARA = {'address_latitude': 39.7747231, 'address_longitude': 64.4198412}


@patch('users.orders.views.notify_message')
class OrderLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name_ru='Протеин', name_uz='Protein', price=100_000, quantity=10,
            slug='order-location-product', country_ru='Узбекистан', country_uz='O‘zbekiston',
        )

    def test_delivery_order_persists_and_returns_numeric_location(self, notify):
        payload = self.payload(**BUKHARA, address_label='  Ляби-Хауз  ')

        response = self.post_order(payload, 'order-location-0001', self.authorization())

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        self.assertEqual(order.address_latitude, Decimal('39.774723'))
        self.assertEqual(order.address_longitude, Decimal('64.419841'))
        self.assertEqual(order.address_label, 'Ляби-Хауз')
        self.assertEqual(order.address, 'Бухара, ул. Накшбанди 5, кв. 3')
        notify.assert_called_once()

        history = self.client.get('/api/v1/users/orders/', headers={'Authorization': self.token})
        serialized = history.json()['data'][0]
        self.assertIsInstance(serialized['address_latitude'], float)
        self.assertEqual(serialized['address_latitude'], 39.774723)
        self.assertEqual(serialized['address_longitude'], 64.419841)
        self.assertEqual(serialized['address_label'], 'Ляби-Хауз')

    def test_order_without_location_returns_nulls(self, _notify):
        response = self.post_order(self.payload(), 'order-location-0002', self.authorization())

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        self.assertIsNone(order.address_latitude)
        self.assertEqual(order.address_label, '')
        serialized = self.client.get(
            '/api/v1/users/orders/', headers={'Authorization': self.token},
        ).json()['data'][0]
        self.assertIsNone(serialized['address_latitude'])
        self.assertIsNone(serialized['address_longitude'])
        self.assertEqual(serialized['address_label'], '')

    def test_invalid_locations_are_rejected(self, notify):
        cases = [
            self.payload(address_latitude=39.77),
            self.payload(address_latitude=None, address_longitude=64.42),
            self.payload(address_latitude=55.75, address_longitude=37.61),
            self.payload(address_latitude=0, address_longitude=0),
            self.payload(address_latitude=91, address_longitude=64.42),
            self.payload(address_latitude=True, address_longitude=64.42),
            self.payload(address_latitude='39.77', address_longitude='64.42'),
            self.payload(**BUKHARA, address_label='x' * 256),
            self.payload(type='pickup', address='-', **BUKHARA),
            self.payload(type='pickup', address='-', address_label='Дом'),
        ]
        for index, payload in enumerate(cases):
            with self.subTest(index=index):
                response = self.post_order(payload, 'order-location-bad-{:04d}'.format(index))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        notify.assert_not_called()

    def test_pickup_accepts_empty_location_fields(self, _notify):
        payload = self.payload(
            type='pickup', address='-', address_latitude=None, address_longitude=None, address_label='',
        )

        self.assertEqual(self.post_order(payload, 'order-location-0003').status_code, 201)

    def test_location_is_part_of_the_idempotency_fingerprint(self, notify):
        first = self.post_order(self.payload(**BUKHARA), 'order-location-0004')
        replay = self.post_order(self.payload(**BUKHARA), 'order-location-0004')
        moved = self.payload(address_latitude=39.78, address_longitude=64.42)
        conflict = self.post_order(moved, 'order-location-0004')
        noted = self.post_order(self.payload(**BUKHARA, customer_note='Позвонить'), 'order-location-0004')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.headers['Idempotency-Replayed'], 'true')
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(noted.status_code, 409)
        self.assertEqual(Order.objects.count(), 1)
        notify.assert_called_once()

    def test_orders_fingerprinted_before_v2_still_replay(self, notify):
        payload = self.payload(customer_note='Позвонить')
        first = self.post_order(payload, 'order-location-legacy-0001')
        order = Order.objects.get()
        command = {**payload, 'phone': '+998901234567'}
        legacy = legacy_request_fingerprint(command, None)
        self.assertEqual(legacy, self.pre_v2_fingerprint(command))
        Order.objects.filter(pk=order.pk).update(request_fingerprint=legacy)

        replay = self.post_order(payload, 'order-location-legacy-0001')
        located = self.post_order(self.payload(**BUKHARA), 'order-location-legacy-0001')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(located.status_code, 409)
        self.assertEqual(order.idempotency_digest, idempotency_digest('order-location-legacy-0001'))
        notify.assert_called_once()

    def test_database_rejects_half_a_coordinate_pair(self, _notify):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(
                type='dcb', full_name='Half Pair', phone='+998901234567', address_latitude='39.77',
            )

    @staticmethod
    def pre_v2_fingerprint(command):
        # Verbatim canonical form used before delivery/location fields were added.
        canonical = json.dumps(
            {
                'actorId': None,
                'fullName': command['full_name'],
                'phone': command['phone'],
                'address': command['address'],
                'type': command['type'],
                'baskets': command['baskets'],
                'couponCode': command.get('coupon_code'),
                'integrationCartToken': command.get('integration_cart_token'),
            },
            ensure_ascii=False, separators=(',', ':'), sort_keys=True,
        )
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def payload(self, **overrides):
        return {
            'full_name': 'Test Customer',
            'phone': '+998 (90) 123-45-67',
            'address': 'Бухара, ул. Накшбанди 5, кв. 3',
            'type': 'dcb',
            'baskets': [{'product': self.product.pk, 'quantity': 1}],
            'coupon_code': None,
            **overrides,
        }

    def authorization(self):
        user = User.objects.create_user(
            username='location-user', email='location@example.test', phone='+998901112299',
            password='safe-test-password', bonus_used=True,
        )
        self.token = 'Token {}'.format(Token.objects.create(user=user).key)
        return self.token

    def post_order(self, payload, key, authorization=None):
        return self.client.post(
            '/api/v1/users/orders/',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Idempotency-Key': key, **({'Authorization': authorization} if authorization else {})},
        )
