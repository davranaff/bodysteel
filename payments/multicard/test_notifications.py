import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from payments.models import Payment
from payments.multicard.fixtures import MULTICARD_SETTINGS, make_order
from payments.multicard.test_callbacks import CALLBACK_URL, callback_body
from store.models import Product
from teleg.utils.notify_message import PAID_LINE, format_order_notification


ORDER_BODY = {
    'full_name': 'Multicard Customer',
    'phone': '+998901234560',
    'address': 'Pickup point',
    'type': 'pickup',
}


class PrepaidOrderNotificationTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name_ru='Протеин уведомления', name_uz='Protein xabar', price=100_000, quantity=5,
            slug='mc-notify-product', country_ru='Узбекистан', country_uz='O‘zbekiston',
        )

    def create_order(self, key):
        return self.client.post(
            '/api/v1/users/orders/',
            data=json.dumps({**ORDER_BODY, 'baskets': [{'product': self.product.pk, 'quantity': 1}]}),
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=key,
        )

    @override_settings(**MULTICARD_SETTINGS)
    @patch('users.orders.views.notify_message')
    def test_prepaid_order_is_not_announced_before_payment(self, notify):
        self.assertEqual(self.create_order('checkout-notify-key-0001').status_code, 201)
        notify.assert_not_called()

    @override_settings(MULTICARD_ENABLED=False)
    @patch('users.orders.views.notify_message')
    def test_without_online_payment_orders_are_announced_at_once(self, notify):
        self.assertEqual(self.create_order('checkout-notify-key-0002').status_code, 201)
        notify.assert_called_once()


@override_settings(**MULTICARD_SETTINGS)
class PaidOrderNotificationTests(TestCase):
    def setUp(self):
        self.order, self.payment = make_order(slug='mc-paid-notify')
        self.payment.provider = 'multicard'
        self.payment.status = Payment.PENDING
        self.payment.save()

    @patch('payments.multicard.notifications.notify_message')
    def test_staff_are_notified_once_after_the_payment_commits(self, notify):
        body = json.dumps(callback_body(self.payment))
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.client.post(CALLBACK_URL, data=body, content_type='application/json')
        self.assertEqual(len(callbacks), 1)
        notify.assert_called_once()
        order, _baskets, _coupon = notify.call_args.args
        self.assertEqual(order.pk, self.order.pk)
        self.assertTrue(notify.call_args.kwargs['paid'])

        with self.captureOnCommitCallbacks(execute=True) as replay:
            self.client.post(CALLBACK_URL, data=body, content_type='application/json')
        self.assertEqual(replay, [])
        notify.assert_called_once()

    @patch('payments.multicard.notifications.notify_message', side_effect=RuntimeError('telegram down'))
    def test_a_failed_alert_does_not_undo_the_payment(self, _notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                CALLBACK_URL, data=json.dumps(callback_body(self.payment)), content_type='application/json',
            )
        self.assertEqual(response.json(), {'success': True})
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'paid')

    def test_paid_alert_is_marked_in_the_message(self):
        baskets = list(self.order.baskets.select_related('product'))
        self.assertIn(PAID_LINE, format_order_notification(self.order, baskets, paid=True))
        self.assertNotIn(PAID_LINE, format_order_notification(self.order, baskets))
