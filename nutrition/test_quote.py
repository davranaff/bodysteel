import json
from datetime import time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token

from nutrition.models import DeliveryMethod, DeliverySlot, DeliveryZone, NutritionProfile
from store.models import Coupon, Order, Product
from users.models import User
from users.orders import test_idempotency


QUOTE_URL = '/api/v1/nutrition/checkout/quote/'


class CheckoutQuoteDiscountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name_ru='Протеин', name_uz='Protein', price=200_000, discounted_price=10_000, quantity=10,
            slug='quote-discount-product', country_ru='Узбекистан', country_uz='O‘zbekiston',
        )
        test_idempotency.OrderIdempotencyTests.create_menu(bonus=50_000)
        cls.coupon = Coupon.objects.create(code='SAVE15', discount_percent=15, max_uses=5)

    def test_anonymous_quote_keeps_legacy_keys_and_applies_coupon_only(self):
        data = self.quote({'coupon_code': 'save15'}).json()['data']

        self.assertEqual(data['subtotal'], 380_000)
        self.assertEqual(data['bonus_discount'], 0)
        self.assertEqual(data['coupon_discount'], 57_000)
        self.assertIs(data['coupon_applied'], True)
        self.assertEqual(data['discount'], 57_000)
        self.assertEqual(data['delivery_fee'], 0)
        self.assertEqual(data['total'], 323_000)
        for key in ('currency', 'delivery_method_code', 'delivery_zone_code', 'delivery_slot', 'language'):
            self.assertIn(key, data)

    def test_unknown_used_or_missing_coupon_is_not_an_error(self):
        Coupon.objects.create(code='USEDUP', discount_percent=50, max_uses=1, used_count=1)
        for coupon_code in ('NOPE', 'USEDUP', '', None):
            with self.subTest(coupon_code=coupon_code):
                response = self.quote({'coupon_code': coupon_code})
                self.assertEqual(response.status_code, 200)
                data = response.json()['data']
                self.assertIs(data['coupon_applied'], False)
                self.assertEqual(data['coupon_discount'], 0)
                self.assertEqual(data['total'], 380_000)
        self.assertEqual(self.quote({'coupon_code': 'X' * 21}).status_code, 400)

    def test_authenticated_quote_matches_the_created_order(self):
        token = self.member_token()
        quote = self.quote({'coupon_code': 'SAVE15'}, token).json()['data']

        self.assertEqual(quote['bonus_discount'], 50_000)
        # Coupon applies after the bonus: int(330 000 * 0.15).
        self.assertEqual(quote['coupon_discount'], 49_500)
        self.assertEqual(quote['discount'], 99_500)
        self.assertEqual(quote['total'], 280_500)

        with patch('users.orders.views.notify_message'):
            created = self.client.post(
                '/api/v1/users/orders/',
                data=json.dumps({
                    'full_name': 'Quote Customer', 'phone': '+998901234567', 'address': '-',
                    'type': 'pickup', 'baskets': self.baskets(), 'coupon_code': 'SAVE15',
                }),
                content_type='application/json',
                headers={'Idempotency-Key': 'quote-matches-order-0001', 'Authorization': token},
            )
        self.assertEqual(created.status_code, 201)
        order = Order.objects.get()
        self.assertEqual(order.total_price, quote['total'])
        self.assertEqual(order.discount_price, quote['discount'])

        after = self.quote({'coupon_code': 'SAVE15'}, token).json()['data']
        self.assertEqual(after['bonus_discount'], 0)
        self.assertEqual(after['coupon_discount'], 57_000)

    def test_quote_has_no_side_effects(self):
        token = self.member_token()
        self.quote({'coupon_code': 'SAVE15'}, token)

        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.used_count, 0)
        self.assertFalse(User.objects.get(username='quote-member').bonus_used)

    def test_conflicts_carry_stable_problem_codes(self):
        zone = DeliveryZone.objects.create(code='center', name_ru='Центр', name_uz='Markaz')
        DeliveryMethod.objects.create(code='city-courier', name_ru='Курьер', name_uz='Kuryer', minimum_order=10**9)
        DeliveryMethod.objects.create(code='express', name_ru='Экспресс', name_uz='Ekspress')
        restricted = DeliveryMethod.objects.create(code='frozen', name_ru='Холод', name_uz='Sovuq')
        profile = NutritionProfile.objects.create(product=self.product)
        profile.allowed_delivery_methods.add(restricted)
        past = DeliverySlot.objects.create(
            zone=zone, delivery_date=timezone.localdate() - timedelta(days=1),
            starts_at=time(10), ends_at=time(12), capacity=5,
        )
        cases = {
            'out_of_stock': {'baskets': [{'product': self.product.pk, 'quantity': 11}]},
            'minimum_order': {'type': 'dcb'},
            'method_not_allowed': {'type': 'dcb', 'delivery_method_code': 'express'},
            'slot_unavailable': {
                'type': 'dcb', 'delivery_method_code': 'frozen',
                'delivery_zone_code': 'center', 'delivery_slot_id': past.pk,
            },
        }
        for code, overrides in cases.items():
            with self.subTest(code=code):
                response = self.quote(overrides)
                self.assertEqual(response.status_code, 409)
                body = response.json()
                self.assertEqual(body['error']['code'], code)
                self.assertEqual(body['detail'], body['error']['message'])

    def quote(self, overrides, authorization=None):
        return self.client.post(
            QUOTE_URL,
            data=json.dumps({'baskets': self.baskets(), 'type': 'pickup', **overrides}),
            content_type='application/json',
            headers={'Authorization': authorization} if authorization else {},
        )

    def baskets(self):
        return [{'product': self.product.pk, 'quantity': 2}]

    @staticmethod
    def member_token():
        user = User.objects.create_user(
            username='quote-member', email='quote-member@example.test', phone='+998901110001',
            password='safe-test-password',
        )
        return 'Token {}'.format(Token.objects.create(user=user).key)
