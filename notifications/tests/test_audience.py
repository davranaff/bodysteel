from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from courses.models import Course, CourseAccess
from notifications.querysets.audience import audience_devices
from notifications.serializers.audience import AudienceSerializer
from notifications.tests.fixtures import PUSH_SETTINGS, category, device, product, purchase, shopper
from store.models import Basket, Favorite


@override_settings(**PUSH_SETTINGS)
class AudienceTests(TestCase):
    def setUp(self):
        self.a, self.b = shopper(1), shopper(2)
        self.device_a = device(self.a)
        self.device_b = device(self.b, platform='ios', model='iPhone18,2', language='uz')

    def users(self, filters):
        return set(audience_devices(filters).values_list('user_id', flat=True))

    def test_device_language_and_staff_defaults(self):
        self.assertEqual(self.users({'platforms': ['ios'], 'languages': ['uz']}), {self.b.pk})
        self.a.is_staff = True
        self.a.save(update_fields=['is_staff'])
        self.assertEqual(self.users({}), {self.b.pk})
        self.assertEqual(self.users({'include_staff': True}), {self.a.pk, self.b.pk})

    def test_opt_out_stale_deleted_and_inactive_never_receive(self):
        self.device_a.marketing_opt_in = False
        self.device_a.save()
        self.device_b.last_seen_at = timezone.now() - timedelta(days=91)
        self.device_b.save()
        self.assertEqual(self.users({}), set())
        self.device_a.marketing_opt_in = True
        self.device_a.save()
        self.a.deleted_at = timezone.now()
        self.a.save()
        self.assertEqual(self.users({}), set())

    def test_one_device_per_user_is_deterministic(self):
        newer = device(self.a, model='Pixel 9')
        selected = audience_devices({'one_device_per_user': True, 'platforms': ['android']})
        self.assertEqual(list(selected.values_list('pk', flat=True)), [newer.pk])

    def test_last_purchase_is_not_any_historical_purchase(self):
        first, second = product(1), product(2)
        earlier = purchase(self.a, first)
        later = purchase(self.a, second)
        from store.models import Order
        Order.objects.filter(pk=earlier.pk).update(created_at=timezone.now() - timedelta(days=5))
        self.assertEqual(self.users({'purchased_product_ids': [first.pk]}), {self.a.pk})
        self.assertEqual(self.users({'last_purchase_product_ids': [first.pk]}), set())
        self.assertEqual(self.users({'last_purchase_product_ids': [second.pk]}), {self.a.pk})

    def test_counts_and_spend_are_not_multiplied_by_items_or_devices(self):
        item = product()
        purchase(self.a, item, total_price=200000)
        purchase(self.a, item, total_price=300000)
        device(self.a)
        self.assertEqual(self.users({'order_count_min': 2, 'order_count_max': 2, 'spend_min': 500000, 'spend_max': 500000}), {self.a.pk})
        self.assertEqual(self.users({'order_count_max': 0}), {self.b.pk})

    def test_unpaid_and_refunded_are_not_purchases(self):
        from store.models import Order
        order = purchase(self.a)
        Order.objects.filter(pk=order.pk).update(status='moderation', payment_status='unpaid')
        self.assertEqual(self.users({'order_count_min': 1}), set())
        self.assertEqual(self.users({'order_scope': 'all', 'order_count_min': 1}), {self.a.pk})
        Order.objects.filter(pk=order.pk).update(payment_status='refunded', status='purchased')
        self.assertEqual(self.users({'order_count_min': 1}), set())

    def test_product_and_category_match_same_item(self):
        category_a, category_b = category(1), category(2)
        item_a, item_b = product(1, category_a), product(2, category_b)
        order = purchase(self.a, item_a)
        Basket.objects.create(user=self.a, order=order, product=item_b, quantity=1)
        self.assertEqual(self.users({'purchased_product_ids': [item_a.pk], 'purchased_category_ids': [category_b.pk]}), set())

    def test_cart_favorites_and_verification(self):
        item = product()
        Basket.objects.create(user=self.a, product=item, quantity=1)
        Favorite.objects.create(user=self.b, product=item)
        self.a.phone_verified_at = timezone.now()
        self.a.save()
        self.assertEqual(self.users({'has_cart': True, 'phone_verified': True}), {self.a.pk})
        self.assertEqual(self.users({'favorite_product_ids': [item.pk]}), {self.b.pk})
        self.assertEqual(self.users({'has_cart': False, 'has_favorites': True}), {self.b.pk})

    def test_active_course_access_excludes_expired(self):
        course = Course.objects.create(slug='synthetic', title_ru='Test', title_uz='Test', price=100000)
        CourseAccess.objects.create(user=self.a, course=course, status='active')
        CourseAccess.objects.create(user=self.b, course=course, status='active', expires_at=timezone.now() - timedelta(days=1))
        self.assertEqual(self.users({'course_ids': [course.pk]}), {self.a.pk})

    def test_unknown_demographics_and_bad_ranges_fail_closed(self):
        for values in ({'age_min': 18}, {'weight': 75}, {'order_count_min': 4, 'order_count_max': 1}):
            self.assertFalse(AudienceSerializer(data=values).is_valid())
