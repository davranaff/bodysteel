from django.test import TestCase

from courses.models import Course, CoursePurchase
from courses.services import create_purchase
from payments.models import Payment
from payments.services import complete_payment
from store.models import Order
from users.models import User


class PaymentFulfillmentTests(TestCase):
    def test_repeated_completion_does_not_duplicate_access(self):
        user = User.objects.create_user(
            username='payment-user', email='payment@example.test', phone='+998901234568', password='password123',
        )
        course = Course.objects.create(
            slug='payment-course', title_ru='Course', title_uz='Kurs', summary_ru='Summary', summary_uz='Dastur',
            price=1000, status=Course.PUBLISHED,
        )
        purchase, payment, _ = create_purchase(user, course.slug, 'payment-test-key-1234')
        complete_payment(payment.pk, 'provider-1')
        complete_payment(payment.pk, 'provider-1')
        self.assertEqual(Payment.objects.filter(course_purchase=purchase, status=Payment.SUCCEEDED).count(), 1)
        self.assertEqual(purchase.course.access_grants.count(), 1)

    def test_repeated_order_payment_marks_the_existing_order_paid(self):
        order = Order.objects.create(
            total_price=200_000,
            type='pickup',
            full_name='Payment Test Customer',
            phone='+998901234569',
            address='-',
        )
        payment = Payment.objects.create(
            order=order,
            provider='manual',
            amount=order.total_price,
            currency='UZS',
        )

        first = complete_payment(payment.pk, 'order-provider-1')
        replay = complete_payment(payment.pk, 'order-provider-1')

        order.refresh_from_db()
        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(Payment.objects.filter(order=order).count(), 1)
        self.assertEqual(Payment.objects.get(pk=payment.pk).status, Payment.SUCCEEDED)
        self.assertEqual(order.payment_status, 'paid')
