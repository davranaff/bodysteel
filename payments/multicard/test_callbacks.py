import hashlib
import json

from django.test import SimpleTestCase, TestCase, override_settings

from payments.models import Payment, PaymentEvent
from payments.multicard.fixtures import MULTICARD_SETTINGS, PAYMENT_UUID, SECRET, make_order
from payments.multicard.signatures import (
    callback_signature,
    verify_callback_signature,
    verify_webhook_signature,
)


CALLBACK_URL = '/api/v1/payments/multicard/callback/'
WEBHOOK_URL = '/api/v1/payments/multicard/webhook/'
OTHER_UUID = 'aaaaaaaa-b9fe-11ef-b159-005056b4367d'


class MulticardSignatureTests(SimpleTestCase):
    def test_callback_signature_matches_the_documented_md5_formula(self):
        # docs.multicard.uz "Callback (success)": md5("{store_id}{invoice_id}{amount}{secret}")
        expected = hashlib.md5('6BS-1220000{}'.format(SECRET).encode()).hexdigest()
        self.assertEqual(callback_signature(6, 'BS-12', 20000, SECRET), expected)
        payload = {'store_id': 6, 'invoice_id': 'BS-12', 'amount': 20000, 'sign': expected.upper()}
        self.assertTrue(verify_callback_signature(payload, SECRET))
        self.assertFalse(verify_callback_signature({**payload, 'amount': 20001}, SECRET))
        self.assertFalse(verify_callback_signature(payload, 'another-secret'))
        self.assertFalse(verify_callback_signature({**payload, 'sign': None}, SECRET))

    def test_webhook_accepts_both_documented_forms_only_with_the_secret(self):
        base = {'uuid': PAYMENT_UUID, 'invoice_id': 'BS-12', 'amount': 20000}
        md5 = hashlib.md5('{}20000{}'.format(PAYMENT_UUID, SECRET).encode()).hexdigest()
        sha1 = hashlib.sha1('{}BS-1220000{}'.format(PAYMENT_UUID, SECRET).encode()).hexdigest()
        self.assertTrue(verify_webhook_signature({**base, 'sign': md5}, SECRET))
        self.assertTrue(verify_webhook_signature({**base, 'sign': sha1}, SECRET))
        self.assertFalse(verify_webhook_signature({**base, 'sign': sha1}, 'wrong'))
        self.assertFalse(verify_webhook_signature({**base, 'sign': 'f' * 40}, SECRET))


def callback_body(payment, amount=None, uuid=PAYMENT_UUID, store_id=6, sign=None):
    amount = payment.amount * 100 if amount is None else amount
    invoice_id = 'BS-{}'.format(payment.pk)
    return {
        'store_id': store_id, 'amount': amount, 'invoice_id': invoice_id, 'billing_id': '2024',
        'payment_time': '2026-11-05 12:00:00', 'phone': '998901234567', 'card_pan': '860053******8829',
        'ps': 'uzcard', 'card_token': 'tok', 'uuid': uuid, 'receipt_url': 'https://dev-checkout.multicard.uz/check/x',
        'sign': sign or callback_signature(store_id, invoice_id, amount, SECRET),
    }


@override_settings(**MULTICARD_SETTINGS)
class MulticardCallbackTests(TestCase):
    def setUp(self):
        self.order, self.payment = make_order()
        self.payment.provider = 'multicard'
        self.payment.status = Payment.PENDING
        self.payment.save()

    def post(self, body, url=CALLBACK_URL):
        return self.client.post(url, data=json.dumps(body), content_type='application/json')

    def test_valid_callback_marks_order_paid_and_replay_is_idempotent(self):
        first = self.post(callback_body(self.payment))
        replay = self.post(callback_body(self.payment))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {'success': True})
        self.assertEqual(replay.json(), {'success': True})
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.SUCCEEDED)
        self.assertEqual(self.payment.provider_payment_id, PAYMENT_UUID)
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(PaymentEvent.objects.filter(payment=self.payment).count(), 1)

    def test_bad_signature_is_rejected_without_state_change(self):
        response = self.post(callback_body(self.payment, sign='0' * 32))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PENDING)

    def test_amount_mismatch_and_wrong_store_are_refused(self):
        wrong_amount = self.post(callback_body(self.payment, amount=self.payment.amount * 100 - 1))
        wrong_store = self.post(callback_body(self.payment, store_id=7))
        self.assertFalse(wrong_amount.json()['success'])
        self.assertEqual(wrong_store.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PENDING)

    def test_second_transaction_for_a_paid_order_is_refused_so_it_is_refunded(self):
        self.post(callback_body(self.payment))
        duplicate = self.post(callback_body(self.payment, uuid=OTHER_UUID))
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json(), {'success': False, 'message': 'Заказ уже оплачен'})
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.provider_payment_id, PAYMENT_UUID)

    def test_unknown_invoice_and_malformed_bodies_are_refused(self):
        body = callback_body(self.payment)
        body['invoice_id'] = 'BS-999999'
        body['sign'] = callback_signature(6, 'BS-999999', body['amount'], SECRET)
        self.assertFalse(self.post(body).json()['success'])
        malformed = self.client.post(CALLBACK_URL, data='not json', content_type='application/json')
        self.assertEqual(malformed.status_code, 400)

    def test_failed_payment_can_still_be_completed_by_a_late_success(self):
        self.payment.status = Payment.FAILED
        self.payment.save()
        self.assertTrue(self.post(callback_body(self.payment)).json()['success'])
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.SUCCEEDED)

    @override_settings(MULTICARD_ENABLED=False)
    def test_disabled_integration_refuses_callbacks(self):
        self.assertEqual(self.post(callback_body(self.payment)).status_code, 503)

    @override_settings(MULTICARD_CALLBACK_ALLOWED_IPS=('195.158.26.90',))
    def test_ip_allowlist_is_enforced_when_configured(self):
        self.assertEqual(self.post(callback_body(self.payment)).status_code, 400)
        allowed = self.client.post(
            CALLBACK_URL, data=json.dumps(callback_body(self.payment)), content_type='application/json',
            REMOTE_ADDR='195.158.26.90',
        )
        self.assertTrue(allowed.json()['success'])

    def test_webhook_error_then_revert_transitions(self):
        amount = self.payment.amount * 100
        invoice_id = 'BS-{}'.format(self.payment.pk)

        def webhook(status, uuid=PAYMENT_UUID):
            sign = hashlib.md5('{}{}{}'.format(uuid, amount, SECRET).encode()).hexdigest()
            return {'uuid': uuid, 'invoice_id': invoice_id, 'amount': amount, 'status': status, 'sign': sign}

        self.assertEqual(self.post(webhook('error'), WEBHOOK_URL).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'failed')

        self.post(callback_body(self.payment))
        self.post(webhook('revert'), WEBHOOK_URL)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.REFUNDED)
        self.assertEqual(self.order.payment_status, 'refunded')

        forged = webhook('success')
        forged['sign'] = 'a' * 32
        self.assertEqual(self.post(forged, WEBHOOK_URL).status_code, 400)
