from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from courses.models import Course, CourseAccess, CoursePurchase
from payments.models import Payment
from payments.multicard.configuration import multicard_enabled
from payments.multicard.fixtures import (
    COURSE_IKPU,
    COURSE_PACKAGE_CODE,
    COURSE_SETTINGS,
    INVOICE_UUID,
    FakeClient,
    make_course,
    make_customer,
)
from payments.multicard.status_token import read_status_token


def checkout_url(slug):
    return '/api/v1/courses/{}/checkout/'.format(slug)


@override_settings(**COURSE_SETTINGS)
class CourseCheckoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.fake = FakeClient()
        patcher = patch('payments.multicard.course_checkout.MulticardClient', return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user, self.api = make_customer()
        self.course = make_course()

    def checkout(self, api=None, slug=None):
        return (api or self.api).post(checkout_url(slug or self.course.slug), {}, format='json', HTTP_ACCEPT_LANGUAGE='uz')

    def test_paid_course_gets_one_invoice_with_a_course_receipt_and_a_retry_reuses_it(self):
        first = self.checkout()
        retry = self.checkout()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        data = first.json()['data']
        payment = Payment.objects.get()
        self.assertEqual(data['status'], 'payment')
        self.assertEqual(data['course_slug'], self.course.slug)
        self.assertEqual(data['checkout_url'], 'https://checkout.multicard.test/invoice/{}'.format(INVOICE_UUID))
        self.assertEqual(read_status_token(data['status_token']), payment.pk)
        self.assertEqual(retry.json()['data']['checkout_url'], data['checkout_url'])
        self.assertEqual(len(self.fake.created), 1)

        body = self.fake.created[0]
        self.assertEqual(body['amount'], 25_000_000)
        self.assertEqual(body['invoice_id'], 'BS-{}'.format(payment.pk))
        self.assertEqual(body['lang'], 'uz')
        self.assertTrue(body['return_url'].startswith('https://shop.example.test/payment/multicard/'))
        self.assertEqual(body['ofd'], [{
            'qty': 1, 'price': 25_000_000, 'total': 25_000_000, 'mxik': COURSE_IKPU,
            'package_code': COURSE_PACKAGE_CODE, 'name': self.course.title_ru,
        }])
        purchase = CoursePurchase.objects.get()
        self.assertEqual(purchase.status, CoursePurchase.PENDING)
        self.assertEqual((payment.provider, payment.status, payment.course_purchase_id), ('multicard', 'pending', purchase.pk))
        self.assertFalse(CourseAccess.objects.exists())

    def test_two_shoppers_can_buy_the_same_course(self):
        _, other = make_customer('second-buyer', '+998901110002')
        self.assertEqual(self.checkout().status_code, 201)
        self.assertEqual(self.checkout(other).status_code, 201)
        self.assertEqual(CoursePurchase.objects.count(), 2)

    def test_owned_course_opens_without_payment(self):
        CourseAccess.objects.create(user=self.user, course=self.course, source='manual')
        response = self.checkout()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'], {'status': 'owned', 'course_slug': self.course.slug})
        self.assertEqual(self.fake.created, [])
        self.assertFalse(CoursePurchase.objects.exists())

    @override_settings(MULTICARD_ENABLED=False)
    def test_free_course_opens_at_once_without_online_payment(self):
        self.course.price = 0
        self.course.save()
        opened = self.checkout()
        again = self.checkout()

        self.assertEqual(opened.status_code, 201)
        self.assertEqual(opened.json()['data'], {'status': 'opened', 'course_slug': self.course.slug})
        self.assertEqual(again.json()['data']['status'], 'owned')
        self.assertTrue(CourseAccess.objects.get(user=self.user).is_active())
        self.assertEqual(CoursePurchase.objects.get().status, CoursePurchase.PAID)
        self.assertEqual(Payment.objects.get().provider, 'free')
        self.assertEqual(self.fake.created, [])

    @override_settings(MULTICARD_COURSE_IKPU='')
    def test_missing_course_receipt_codes_make_payment_unavailable_and_write_nothing(self):
        response = self.checkout()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'payment_unavailable')
        self.assertFalse(CoursePurchase.objects.exists())
        self.assertFalse(Payment.objects.exists())

    @override_settings(MULTICARD_COURSE_PACKAGE_CODE='not-a-code')
    def test_a_bad_course_code_does_not_turn_off_order_payments(self):
        self.assertTrue(multicard_enabled())
        self.assertEqual(self.checkout().status_code, 503)

    def test_course_off_sale_unknown_course_and_guest(self):
        self.course.status = Course.DRAFT
        self.course.save()
        off_sale = self.checkout()
        self.assertEqual(off_sale.status_code, 409)
        self.assertEqual(off_sale.json()['error']['code'], 'not_on_sale')
        self.assertEqual(self.checkout(slug='missing-course').status_code, 404)
        guest = APIClient().post(checkout_url(self.course.slug), {}, format='json')
        self.assertIn(guest.status_code, (401, 403))
        self.assertEqual(self.checkout().status_code, 409)
        self.assertEqual(self.api.post(checkout_url(self.course.slug), {'x': 1}, format='json').status_code, 400)

    def test_price_change_cancels_the_old_open_purchase(self):
        self.checkout()
        old_purchase = CoursePurchase.objects.get()
        self.course.price = 300_000
        self.course.save()
        response = self.checkout()

        self.assertEqual(response.status_code, 201)
        old_purchase.refresh_from_db()
        self.assertEqual(old_purchase.status, CoursePurchase.CANCELLED)
        self.assertEqual(old_purchase.payments.get().status, Payment.CANCELLED)
        self.assertEqual(CoursePurchase.objects.exclude(pk=old_purchase.pk).get().amount, 300_000)
        self.assertEqual(self.fake.created[1]['amount'], 30_000_000)

    def test_a_failed_attempt_gets_a_new_invoice_and_the_stale_one_is_cancelled(self):
        self.checkout()
        Payment.objects.update(status=Payment.FAILED)
        response = self.checkout()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.fake.created), 2)
        self.assertEqual(self.fake.cancelled, [INVOICE_UUID])
        self.assertEqual(CoursePurchase.objects.count(), 1)
        self.assertEqual(Payment.objects.get().status, Payment.PENDING)

    def test_expired_access_can_be_bought_again(self):
        CourseAccess.objects.create(
            user=self.user, course=self.course, source='purchase', expires_at=timezone.now() - timedelta(days=1),
        )
        response = self.checkout()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['data']['status'], 'payment')
