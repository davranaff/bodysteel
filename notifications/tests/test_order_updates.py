from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from notifications.models import PushDelivery, PushDevice
from notifications.policies.order_updates import COPY, ORDER_TARGET_URL
from notifications.services.order_updates import enqueue_order_update
from notifications.tests.fixtures import PUSH_SETTINGS, device, purchase, shopper
from store.models import Order

TRANSITIONS = (
    ('payment_status', 'paid', 'payment_paid'),
    ('payment_status', 'failed', 'payment_failed'),
    ('payment_status', 'refunded', 'payment_refunded'),
    ('fulfillment_status', 'confirmed', 'order_confirmed'),
    ('fulfillment_status', 'preparing', 'order_preparing'),
    ('fulfillment_status', 'ready', 'order_ready'),
    ('fulfillment_status', 'delivering', 'order_delivering'),
    ('fulfillment_status', 'delivered', 'order_delivered'),
    ('fulfillment_status', 'cancelled', 'order_cancelled'),
)


@override_settings(**PUSH_SETTINGS)
class OrderUpdateEnqueueTests(TestCase):
    def setUp(self):
        self.user = shopper()
        # Transactional alerts must not depend on marketing consent.
        self.device = device(self.user, marketing_opt_in=False)
        self.order = purchase(self.user, total_price=987654)

    def change(self, order=None, **values):
        order = order or self.order
        for field, value in values.items():
            setattr(order, field, value)
        with self.captureOnCommitCallbacks(execute=True):
            order.save()
        return order

    def test_each_transition_queues_one_frozen_ru_snapshot(self):
        for field, value, event in TRANSITIONS:
            with self.subTest(event=event):
                order = purchase(self.user)
                self.change(order, **{field: value})
                delivery = PushDelivery.objects.get(order=order)
                title, body = COPY[event]['ru']
                self.assertEqual((delivery.kind, delivery.order_event, delivery.status), ('order_update', event, 'pending'))
                self.assertEqual((delivery.title, delivery.body), (title, body.format(code=order.order_code)))
                self.assertIn(order.order_code, delivery.body)
                self.assertEqual(delivery.target_url, ORDER_TARGET_URL)
                self.assertIsNone(delivery.campaign_id)
                self.assertIsNone(delivery.requested_by_id)
                self.assertEqual(delivery.expected_scope, self.device.registration_scope)
                self.assertLessEqual(delivery.next_attempt_at, timezone.now())

    def test_language_is_taken_per_device(self):
        uzbek = device(self.user, language='uz', marketing_opt_in=False)
        self.change(fulfillment_status='confirmed')
        deliveries = {item.device_id: item for item in PushDelivery.objects.filter(order=self.order)}
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(deliveries[self.device.pk].language, 'ru')
        self.assertEqual(deliveries[self.device.pk].title, 'Заказ подтверждён')
        self.assertEqual(deliveries[uzbek.pk].language, 'uz')
        self.assertEqual(deliveries[uzbek.pk].title, 'Buyurtma tasdiqlandi')
        self.assertEqual(deliveries[uzbek.pk].body,
                         '№{} buyurtmangiz tasdiqlandi. Tez orada uni yig‘ishni boshlaymiz.'.format(self.order.order_code))

    def test_copy_has_no_private_order_data(self):
        self.order.full_name = 'Synthetic Private Name'
        self.order.address = 'Synthetic street 7'
        self.change(payment_status='paid')
        delivery = PushDelivery.objects.get(order=self.order)
        for private in ('987', 'Synthetic', self.user.phone, 'street'):
            self.assertNotIn(private, delivery.title + delivery.body)
        for copies in COPY.values():
            for title, body in copies.values():
                self.assertEqual(body.count('{code}'), 1)
                self.assertNotIn('{', title)

    def test_creation_and_non_notifying_changes_queue_nothing(self):
        with self.captureOnCommitCallbacks(execute=True):
            created = purchase(self.user, payment_status='paid', fulfillment_status='confirmed')
        self.change(created)
        self.change(payment_status='pending')
        self.change(full_name='Changed name')
        self.order.fulfillment_status = 'confirmed'
        with self.captureOnCommitCallbacks(execute=True):
            # Status not listed in update_fields is not persisted, so nothing changed.
            self.order.save(update_fields=('full_name',))
        self.assertFalse(PushDelivery.objects.exists())

    def test_ready_notifies_only_pickup_orders(self):
        courier = purchase(self.user, type='dcb')
        self.change(courier, fulfillment_status='ready')
        self.assertFalse(PushDelivery.objects.exists())
        self.change(courier, fulfillment_status='delivering')
        self.assertEqual(PushDelivery.objects.get().order_event, 'order_delivering')

    def test_one_save_with_two_changes_queues_the_most_important_event(self):
        self.change(fulfillment_status='cancelled', payment_status='refunded')
        self.assertEqual(list(PushDelivery.objects.values_list('order_event', flat=True)), ['payment_refunded'])

    def test_same_order_event_and_device_is_never_queued_twice(self):
        self.change(payment_status='failed')
        self.change(payment_status='pending')
        self.change(payment_status='failed')
        self.assertEqual(enqueue_order_update(self.order, 'payment_failed'), 0)
        self.assertEqual(PushDelivery.objects.filter(order=self.order, order_event='payment_failed').count(), 1)
        self.change(payment_status='paid')
        self.assertEqual(PushDelivery.objects.filter(order=self.order).count(), 2)

    def test_ineligible_devices_and_accounts_receive_nothing(self):
        other = shopper(2)
        device(other, permission='denied')
        stale = device(other)
        PushDevice.objects.filter(pk=stale.pk).update(last_seen_at=timezone.now() - timedelta(days=91))
        order = purchase(other)
        self.change(order, fulfillment_status='confirmed')
        self.assertFalse(PushDelivery.objects.exists())
        for index, values in enumerate(({'is_active': False}, {'deleted_at': timezone.now()}), start=3):
            with self.subTest(values=values):
                owner = shopper(index)
                device(owner)
                order = purchase(owner)
                type(owner).objects.filter(pk=owner.pk).update(**values)
                self.change(order, fulfillment_status='confirmed')
                self.assertFalse(PushDelivery.objects.filter(order=order).exists())

    def test_guest_order_and_disabled_push_queue_nothing(self):
        guest = Order.objects.create(type='pickup', full_name='Guest', phone='+998900000000', total_price=1)
        self.change(guest, payment_status='paid')
        with override_settings(PUSH_ENABLED=False):
            self.change(payment_status='paid')
            self.assertEqual(enqueue_order_update(self.order, 'payment_paid'), 0)
        self.assertFalse(PushDelivery.objects.exists())

    def test_unknown_event_is_rejected(self):
        with self.assertRaises(ValueError):
            enqueue_order_update(self.order, 'order_shipped_to_moon')

    def test_push_failures_never_break_the_order_save(self):
        with patch('notifications.services.order_updates.enqueue_order_update', side_effect=RuntimeError('boom')), \
                self.assertLogs('bodysteel.notifications', 'ERROR'):
            self.change(payment_status='paid')
        with patch('notifications.signals.order_update_event', side_effect=RuntimeError('boom')), \
                self.assertLogs('bodysteel.notifications', 'ERROR'):
            self.change(fulfillment_status='confirmed')
        self.order.refresh_from_db()
        self.assertEqual((self.order.payment_status, self.order.fulfillment_status), ('paid', 'confirmed'))
        self.assertFalse(PushDelivery.objects.exists())

    def test_rolled_back_change_queues_nothing(self):
        from django.db import transaction
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                with transaction.atomic():
                    self.order.payment_status = 'paid'
                    self.order.save()
                    raise RuntimeError('rollback')
            except RuntimeError:
                pass
        self.assertEqual(callbacks, [])
        self.assertFalse(PushDelivery.objects.exists())
