import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from rest_framework.authtoken.models import Token

from payments.models import Payment
from store.models import Basket, Coupon, Menu, Order, Product
from users.models import User


class OrderIdempotencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name_ru='Тестовый протеин',
            name_uz='Test protein',
            price=200_000,
            discounted_price=10_000,
            quantity=5,
            slug='order-idempotency-product',
            country_ru='Узбекистан',
            country_uz='O‘zbekiston',
        )

    @patch('users.orders.views.notify_message')
    def test_exact_replay_returns_same_receipt_and_applies_side_effects_once(self, notify):
        payload = self.payload()
        payload['baskets'] = [
            {'product': self.product.pk, 'quantity': 1},
            {'product': self.product.pk, 'quantity': 1},
        ]

        first = self.post_order(payload, 'checkout-replay-0001')
        replay = self.post_order(self.payload(), 'checkout-replay-0001')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(first.json(), replay.json())
        self.assertEqual(replay.headers['Idempotency-Replayed'], 'true')
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Basket.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 5)
        notify.assert_called_once()

        order = Order.objects.get()
        self.assertNotEqual(order.idempotency_digest, 'checkout-replay-0001')
        self.assertEqual(len(order.idempotency_digest), 64)
        self.assertEqual(len(order.request_fingerprint), 64)

    @patch('users.orders.views.notify_message')
    def test_reused_key_with_different_request_returns_conflict(self, notify):
        first = self.post_order(self.payload(), 'checkout-conflict-0001')
        changed = self.payload()
        changed['address'] = 'Another pickup point'
        conflict = self.post_order(changed, 'checkout-conflict-0001')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(Order.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 5)
        notify.assert_called_once()

    def test_missing_or_ambiguous_idempotency_key_is_rejected(self):
        missing = self.client.post(
            '/api/v1/users/orders/',
            data=json.dumps(self.payload()),
            content_type='application/json',
        )
        invalid = self.post_order(self.payload(), 'contains spaces 0001')

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    @patch('users.orders.views.notify_message')
    def test_guest_order_applies_coupon_without_requiring_registration(self, notify):
        coupon = Coupon.objects.create(
            code='GUEST10',
            discount_percent=10,
            max_uses=2,
        )
        payload = self.payload()
        payload['coupon_code'] = coupon.code.lower()

        response = self.post_order(payload, 'checkout-guest-coupon-0001')

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        self.assertIsNone(order.user)
        self.assertEqual(order.coupon, coupon)
        self.assertEqual(order.subtotal_price, 380_000)
        self.assertEqual(order.discount_price, 38_000)
        self.assertEqual(order.total_price, 342_000)
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 5)
        notify.assert_called_once()

    @patch('users.orders.views.notify_message')
    def test_authenticated_order_applies_unused_bonus_and_coupon(self, notify):
        self.create_menu(bonus=50_000)
        coupon = Coupon.objects.create(
            code='MEMBER10',
            discount_percent=10,
            max_uses=2,
        )
        user = User.objects.create_user(
            username='bonus-order-user',
            email='bonus-order@example.test',
            phone='+998901112234',
            password='safe-test-password',
        )
        authorization = 'Token {}'.format(Token.objects.create(user=user).key)
        payload = self.payload()
        payload['coupon_code'] = coupon.code

        response = self.post_order(
            payload,
            'checkout-member-coupon-0001',
            authorization=authorization,
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        self.assertEqual(order.user, user)
        self.assertEqual(order.coupon, coupon)
        self.assertEqual(order.subtotal_price, 380_000)
        self.assertEqual(order.discount_price, 83_000)
        self.assertEqual(order.total_price, 297_000)
        self.assertEqual(Payment.objects.get(order=order).amount, 297_000)
        user.refresh_from_db()
        coupon.refresh_from_db()
        self.assertTrue(user.bonus_used)
        self.assertEqual(coupon.used_count, 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 5)
        notify.assert_called_once()

    @patch('users.orders.views.notify_message')
    def test_order_history_requires_auth_and_hides_idempotency_state(self, _notify):
        user = User.objects.create_user(
            username='order-history-user',
            email='order-history@example.test',
            phone='+998901112233',
            password='safe-test-password',
            bonus_used=True,
        )
        authorization = 'Token {}'.format(Token.objects.create(user=user).key)
        created = self.post_order(
            self.payload(),
            'checkout-history-0001',
            authorization=authorization,
        )
        history = self.client.get(
            '/api/v1/users/orders/',
            headers={'Authorization': authorization},
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(history.status_code, 200)
        serialized = history.json()['data'][0]
        self.assertNotIn('idempotency_digest', serialized)
        self.assertNotIn('request_fingerprint', serialized)

        self.assertIn(self.client.get('/api/v1/users/orders/').status_code, (401, 403))

    def payload(self):
        return {
            'full_name': 'Test Customer',
            'phone': '+998 (90) 123-45-67',
            'address': '-',
            'type': 'pickup',
            'baskets': [{'product': self.product.pk, 'quantity': 2}],
            'coupon_code': None,
        }

    def post_order(self, payload, idempotency_key, authorization=None):
        return self.client.post(
            '/api/v1/users/orders/',
            data=json.dumps(payload),
            content_type='application/json',
            headers={
                'Idempotency-Key': idempotency_key,
                **({'Authorization': authorization} if authorization else {}),
            },
        )

    @staticmethod
    def create_menu(bonus):
        return Menu.objects.create(
            name='Test menu',
            about_uz='Test',
            about_ru='Test',
            blog_uz='Test',
            blog_ru='Test',
            set_product_uz='Test',
            set_product_ru='Test',
            delivery_and_payment_uz='Test',
            delivery_and_payment_ru='Test',
            bank_card_number='0000000000000000',
            uzbekistan_description_uz='Test',
            bukhara_description_uz='Test',
            uzbekistan_description_ru='Test',
            bukhara_description_ru='Test',
            bonus=bonus,
        )


class OrderIdempotencyConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    @patch('users.orders.views.notify_message')
    def test_concurrent_replay_creates_one_order(self, notify):
        product = Product.objects.create(
            name_ru='Конкурентный товар',
            name_uz='Concurrent product',
            price=100_000,
            quantity=4,
            slug='concurrent-order-product',
            country_ru='Узбекистан',
            country_uz='O‘zbekiston',
        )
        payload = {
            'full_name': 'Concurrent Customer',
            'phone': '+998 (90) 123-45-67',
            'address': '-',
            'type': 'pickup',
            'baskets': [{'product': product.pk, 'quantity': 2}],
            'coupon_code': None,
        }
        barrier = Barrier(2)

        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                response = Client().post(
                    '/api/v1/users/orders/',
                    data=json.dumps(payload),
                    content_type='application/json',
                    headers={'Idempotency-Key': 'checkout-concurrent-0001'},
                )
                return response.status_code, response.json(), response.headers.get('Idempotency-Replayed')
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [future.result(timeout=10) for future in [executor.submit(submit), executor.submit(submit)]]

        self.assertEqual([result[0] for result in results], [201, 201])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual({result[2] for result in results}, {None, 'true'})
        self.assertEqual(Order.objects.count(), 1)
        product.refresh_from_db()
        self.assertEqual(product.quantity, 4)
        notify.assert_called_once()
