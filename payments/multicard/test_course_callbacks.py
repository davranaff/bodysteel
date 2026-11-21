import hashlib
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from courses.models import CourseAccess, CoursePurchase
from payments.models import Payment
from payments.multicard.fixtures import (
    COURSE_SETTINGS,
    PAYMENT_UUID,
    SECRET,
    FakeClient,
    make_course,
    make_customer,
)
from payments.multicard.notifications import format_course_notification, notify_paid_course
from payments.multicard.status_token import issue_status_token
from payments.multicard.test_callbacks import CALLBACK_URL, WEBHOOK_URL, callback_body


@override_settings(**COURSE_SETTINGS)
class CourseCallbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.fake = FakeClient()
        patcher = patch('payments.multicard.course_checkout.MulticardClient', return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user, self.api = make_customer()
        self.course = make_course()
        self.assertEqual(self.checkout().status_code, 201)
        self.payment = Payment.objects.get()
        self.purchase = CoursePurchase.objects.get()

    def checkout(self):
        return self.api.post('/api/v1/courses/{}/checkout/'.format(self.course.slug), {}, format='json')

    def post(self, body, url=CALLBACK_URL):
        return self.client.post(url, data=json.dumps(body), content_type='application/json')

    def webhook(self, status, payment=None, uuid=PAYMENT_UUID):
        payment = payment or self.payment
        amount = payment.amount * 100
        sign = hashlib.md5('{}{}{}'.format(uuid, amount, SECRET).encode()).hexdigest()
        body = {'uuid': uuid, 'invoice_id': 'BS-{}'.format(payment.pk), 'amount': amount, 'status': status, 'sign': sign}
        return self.post(body, WEBHOOK_URL)

    def test_success_opens_the_course_alerts_staff_and_the_status_names_the_course(self):
        with patch('payments.multicard.targets.notify_paid_course') as alert:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.post(callback_body(self.payment))

        self.assertEqual(response.json(), {'success': True})
        alert.assert_called_once_with(self.purchase.pk)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, CoursePurchase.PAID)
        access = CourseAccess.objects.get(user=self.user, course=self.course)
        self.assertTrue(access.is_active())
        self.assertEqual(access.purchase_id, self.purchase.pk)

        status = self.client.get(
            '/api/v1/payments/multicard/status/{}/'.format(issue_status_token(self.payment.pk)),
            HTTP_ACCEPT_LANGUAGE='uz',
        )
        data = status.json()['data']
        self.assertEqual(data['status'], 'paid')
        self.assertEqual(data['kind'], 'course')
        self.assertEqual(data['course_slug'], self.course.slug)
        self.assertEqual(data['course_title'], self.course.title_uz)
        self.assertEqual(data['amount'], 250_000)
        self.assertNotIn('order_id', data)

    def test_wrong_amount_is_refused(self):
        response = self.post(callback_body(self.payment, amount=self.payment.amount * 100 - 100))
        self.assertFalse(response.json()['success'])
        self.assertFalse(CourseAccess.objects.exists())

    def test_payment_for_a_course_opened_another_way_is_refused_so_it_is_returned(self):
        CourseAccess.objects.create(user=self.user, course=self.course, source='manual')
        response = self.post(callback_body(self.payment))
        self.assertEqual(response.json(), {'success': False, 'message': 'Курс уже открыт'})
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PENDING)

    def test_late_payment_of_a_purchase_cancelled_by_a_price_change_is_refused(self):
        self.course.price = 300_000
        self.course.save()
        self.assertEqual(self.checkout().status_code, 201)
        response = self.post(callback_body(self.payment))
        self.assertFalse(response.json()['success'])
        self.assertFalse(CourseAccess.objects.exists())

    def test_error_keeps_the_purchase_open_and_a_refund_closes_the_course(self):
        self.assertEqual(self.webhook('error').status_code, 200)
        self.payment.refresh_from_db()
        self.purchase.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.FAILED)
        self.assertEqual(self.purchase.status, CoursePurchase.PENDING)

        self.assertTrue(self.post(callback_body(self.payment)).json()['success'])
        self.webhook('revert')
        self.payment.refresh_from_db()
        self.purchase.refresh_from_db()
        access = CourseAccess.objects.get(user=self.user, course=self.course)
        self.assertEqual(self.payment.status, Payment.REFUNDED)
        self.assertEqual(self.purchase.status, CoursePurchase.REFUNDED)
        self.assertEqual((access.status, access.revoke_reason), (CourseAccess.REVOKED, 'Оплата возвращена'))

        again = self.checkout()
        self.assertEqual(again.status_code, 201)
        self.assertEqual(again.json()['data']['status'], 'payment')
        self.assertEqual(CoursePurchase.objects.count(), 2)

    def test_repeat_purchase_after_a_refund_opens_the_course_again(self):
        self.post(callback_body(self.payment))
        self.webhook('revert')
        self.checkout()
        second = Payment.objects.exclude(pk=self.payment.pk).get()
        other_uuid = 'bbbbbbbb-b9fe-11ef-b159-005056b4367d'
        self.assertTrue(self.post(callback_body(second, uuid=other_uuid)).json()['success'])
        access = CourseAccess.objects.get(user=self.user, course=self.course)
        self.assertTrue(access.is_active())
        self.assertEqual(access.purchase_id, second.course_purchase_id)


class CourseNotificationTests(TestCase):
    def test_staff_alert_names_the_course_buyer_and_amount_and_escapes_html(self):
        user, _ = make_customer()
        course = make_course(title_ru='Курс <b>X</b>')
        purchase = CoursePurchase.objects.create(
            user=user, course=course, course_title=course.title_ru, amount=1_250_000,
            idempotency_digest='d' * 64,
        )
        text = format_course_notification(purchase)
        self.assertIn('🎓 <b>Оплачен курс</b>', text)
        self.assertIn('Курс &lt;b&gt;X&lt;/b&gt;', text)
        self.assertIn('1 250 000 UZS', text)
        self.assertIn('Азиз Каримов · +998901110001', text)

        with patch('payments.multicard.notifications.ChatModel') as chats, \
                patch('payments.multicard.notifications.bot') as bot:
            chats.objects.values_list.return_value.distinct.return_value = [11, 12]
            bot.send_message.side_effect = [RuntimeError('blocked'), None]
            notify_paid_course(purchase.pk)
        self.assertEqual(bot.send_message.call_count, 2)
