from django.db import IntegrityError, transaction
from django.test import TestCase

from store.models import Coupon


class CouponCaseInsensitiveTests(TestCase):
    def setUp(self):
        self.coupon = Coupon.objects.create(
            code='Summer10',
            discount_percent=10,
            max_uses=5,
        )

    def test_public_validation_ignores_letter_case(self):
        for code in ('summer10', 'SUMMER10', 'SuMmEr10'):
            with self.subTest(code=code):
                response = self.client.get('/api/v1/users/coupons/', {'key': code})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'discount_percent': 10})

    def test_codes_cannot_differ_only_by_letter_case(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Coupon.objects.create(
                code='sUMMER10',
                discount_percent=20,
                max_uses=5,
            )
