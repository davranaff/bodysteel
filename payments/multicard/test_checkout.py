import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.authtoken.models import Token

from payments.models import Payment
from payments.multicard.configuration import require_configuration
from payments.multicard.fixtures import (
    INVOICE_UUID,
    MULTICARD_SETTINGS,
    ORDER_KEY,
    PAYMENT_UUID,
    FakeClient,
    make_order,
)
from payments.multicard.receipt import build_ofd
from payments.multicard.status_token import issue_status_token, read_status_token
from users.models import User


def start_url(order):
    return '/api/v1/payments/orders/{}/multicard/'.format(order.pk)


@override_settings(**MULTICARD_SETTINGS)
class MulticardStartTests(TestCase):
    def setUp(self):
        cache.clear()
        self.fake = FakeClient()
        for target in ('payments.multicard.checkout.MulticardClient', 'payments.multicard.views.MulticardClient'):
            patcher = patch(target, return_value=self.fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def start(self, order, body=None, **headers):
        return self.client.post(
            start_url(order), data=json.dumps(body or {'channel': 'web', 'order_key': ORDER_KEY}),
            content_type='application/json', HTTP_ACCEPT_LANGUAGE='uz', **headers,
        )

    def test_guest_with_order_key_gets_checkout_url_and_retry_reuses_the_invoice(self):
        order, payment = make_order()
        first = self.start(order)
        retry = self.start(order)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        data = first.json()['data']
        self.assertEqual(data['checkout_url'], 'https://checkout.multicard.test/invoice/{}'.format(INVOICE_UUID))
        self.assertEqual(read_status_token(data['status_token']), payment.pk)
        self.assertEqual(retry.json()['data']['checkout_url'], data['checkout_url'])
        self.assertEqual(len(self.fake.created), 1)

        body = self.fake.created[0]
        self.assertEqual(body['store_id'], 6)
        self.assertEqual(body['amount'], order.total_price * 100)
        self.assertEqual(body['invoice_id'], 'BS-{}'.format(payment.pk))
        self.assertEqual(body['lang'], 'uz')
        self.assertTrue(body['return_url'].startswith('https://shop.example.test/payment/multicard/'))
        self.assertEqual(body['callback_url'], MULTICARD_SETTINGS['MULTICARD_CALLBACK_URL'])

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual((payment.provider, payment.status), ('multicard', Payment.PENDING))
        self.assertEqual(order.payment_status, 'pending')

    def test_app_channel_uses_the_app_return_link_and_replaces_the_web_invoice(self):
        order, _ = make_order()
        self.start(order)
        response = self.start(order, {'channel': 'app', 'order_key': ORDER_KEY})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.fake.created[1]['return_url'].startswith('https://shop.example.test/app/payment/'))
        self.assertEqual(self.fake.cancelled, [INVOICE_UUID])

    def test_wrong_or_missing_order_key_hides_the_order(self):
        order, _ = make_order()
        self.assertEqual(self.start(order, {'channel': 'web', 'order_key': 'another-key-00000001'}).status_code, 404)
        self.assertEqual(self.start(order, {'channel': 'web'}).status_code, 404)
        self.assertEqual(self.fake.created, [])

    def test_signed_in_owner_can_pay_without_the_order_key_but_others_cannot(self):
        owner = User.objects.create_user(username='mc-owner', email='o@example.test', phone='+998901110001', password='x' * 12)
        other = User.objects.create_user(username='mc-other', email='p@example.test', phone='+998901110002', password='x' * 12)
        order, _ = make_order(user=owner)
        stranger = self.start(order, {'channel': 'web'}, HTTP_AUTHORIZATION='Token {}'.format(Token.objects.create(user=other).key))
        mine = self.start(order, {'channel': 'web'}, HTTP_AUTHORIZATION='Token {}'.format(Token.objects.create(user=owner).key))
        self.assertEqual(stranger.status_code, 404)
        self.assertEqual(mine.status_code, 201)

    def test_paid_order_and_unknown_fields_are_refused(self):
        order, payment = make_order()
        payment.status = Payment.SUCCEEDED
        payment.save()
        paid = self.start(order)
        self.assertEqual(paid.status_code, 409)
        self.assertEqual(paid.json()['error']['code'], 'already_paid')
        unknown = self.start(order, {'channel': 'web', 'order_key': ORDER_KEY, 'amount': 1})
        self.assertEqual(unknown.status_code, 400)

    @override_settings(MULTICARD_ENABLED=False)
    def test_disabled_gateway_is_reported_as_unavailable(self):
        order, _ = make_order()
        response = self.start(order)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'payment_unavailable')
        methods = self.client.get('/api/v1/payments/methods/')
        self.assertEqual(methods.json(), {'data': {'multicard': False}})

    def test_status_page_reconciles_a_missing_callback_by_polling_multicard(self):
        order, payment = make_order()
        token = self.start(order).json()['data']['status_token']
        self.fake.status, self.fake.payment_uuid = 'success', PAYMENT_UUID
        response = self.client.get('/api/v1/payments/multicard/status/{}/'.format(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['status'], 'paid')
        self.assertEqual(response.json()['data']['order_code'], order.order_code)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')

    def test_status_token_is_tamper_evident(self):
        order, payment = make_order()
        token = issue_status_token(payment.pk)
        forged = token[:-2] + ('aa' if not token.endswith('aa') else 'bb')
        self.assertEqual(self.client.get('/api/v1/payments/multicard/status/{}/'.format(forged)).status_code, 404)


@override_settings(**MULTICARD_SETTINGS)
class MulticardReceiptTests(TestCase):
    def test_discount_and_delivery_are_allocated_so_lines_sum_to_the_charge(self):
        order, _ = make_order(quantity=3, unit_price=33_333, discount=1_000, delivery_fee=15_000)
        lines = build_ofd(order, list(order.baskets.all()), require_configuration())
        self.assertEqual(sum(line['total'] for line in lines), order.total_price * 100)
        for line in lines:
            self.assertEqual(line['qty'] * line['price'], line['total'])
        self.assertEqual(lines[-1]['name'], 'Доставка')
        self.assertEqual(sum(line['qty'] for line in lines[:-1]), 3)


class MulticardStatusTokenTests(SimpleTestCase):
    def test_round_trip_and_rejection(self):
        self.assertEqual(read_status_token(issue_status_token(42)), 42)
        self.assertIsNone(read_status_token('garbage'))
        self.assertIsNone(read_status_token(None))
