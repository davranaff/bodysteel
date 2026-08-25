from django.test import TestCase

from courses.models import Course, CoursePurchase
from courses.services import create_purchase
from payments.models import Payment
from payments.services import complete_payment
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
