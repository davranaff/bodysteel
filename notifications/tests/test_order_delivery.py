import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token

from notifications.models import PushCampaign, PushDelivery
from notifications.services.campaigns import publish_campaign
from notifications.services.delivery import deliver_pending, due_deliveries
from notifications.services.devices import register_device
from notifications.services.order_updates import enqueue_order_update
from notifications.tests.fixtures import (PUSH_SETTINGS, FakeSender, campaign, device, device_values,
                                          operator, purchase, shopper)
from store.models import Order


@override_settings(**PUSH_SETTINGS)
class OrderUpdateDeliveryTests(TestCase):
    def setUp(self):
        self.user = shopper()
        self.device = device(self.user, marketing_opt_in=False)
        self.order = purchase(self.user)
        self.sender = FakeSender()

    def enqueue(self, event='order_confirmed'):
        self.assertEqual(enqueue_order_update(self.order, event), 1)
        return PushDelivery.objects.get(order=self.order, order_event=event)

    def assert_skipped(self, delivery, code, now=None):
        deliver_pending(sender=self.sender, now=now)
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.failure_code), ('skipped', code))
        self.assertEqual(self.sender.calls, [])

    def test_order_update_is_sent_without_marketing_consent_or_operator(self):
        delivery = self.enqueue()
        self.assertEqual(deliver_pending(sender=self.sender), 1)
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.attempt_count), ('accepted', 1))
        self.assertEqual(len(self.sender.calls), 1)
        self.assertTrue(self.sender.calls[0][0].startswith('synthetic-fcm-'))
        self.assertEqual(deliver_pending(sender=self.sender), 0)

    def test_os_permission_and_device_activity_are_rechecked(self):
        delivery = self.enqueue()
        register_device(self.user, Token.objects.get(user=self.user), self.device.installation_id,
                        device_values(permission='denied'), 'ru')
        self.assert_skipped(delivery, 'device_ineligible')

    def test_transferred_device_cannot_receive_prior_owner_order(self):
        delivery = self.enqueue()
        other = shopper(2)
        register_device(other, Token.objects.create(user=other), self.device.installation_id, device_values(), 'ru')
        self.assert_skipped(delivery, 'device_ineligible')

    def test_session_rotation_skips_order_update(self):
        delivery = self.enqueue()
        Token.objects.filter(user=self.user).delete()
        Token.objects.create(user=self.user)
        self.assert_skipped(delivery, 'session_revoked')

    def test_undecryptable_token_fails_closed(self):
        delivery = self.enqueue()
        from cryptography.fernet import Fernet
        with override_settings(PUSH_TOKEN_ENCRYPTION_KEYS=(Fernet.generate_key().decode(),)):
            deliver_pending(sender=self.sender)
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.failure_code), ('failed', 'token_key_unavailable'))

    def test_deleted_or_reassigned_order_is_not_announced(self):
        delivery = self.enqueue()
        Order.objects.filter(pk=self.order.pk).update(user=shopper(2))
        self.assert_skipped(delivery, 'order_unavailable')
        second = purchase(self.user)
        self.order = second
        delivery = self.enqueue()
        second.delete()
        delivery.refresh_from_db()
        self.assertIsNone(delivery.order_id)
        self.assert_skipped(delivery, 'order_unavailable')

    def test_backlog_older_than_a_day_expires(self):
        delivery = self.enqueue()
        self.assert_skipped(delivery, 'expired', now=timezone.now() + timedelta(hours=25))

    def test_push_disabled_worker_fails_closed(self):
        self.enqueue()
        from notifications.configuration import PushNotConfigured
        with override_settings(PUSH_ENABLED=False), self.assertRaises(PushNotConfigured):
            deliver_pending(sender=self.sender)
        self.assertEqual(PushDelivery.objects.get().status, 'pending')

    def test_campaign_flow_is_unchanged_next_to_order_updates(self):
        actor = operator()
        opted_in = device(shopper(3))
        item = campaign(actor)
        publish_campaign(item.pk, actor)
        self.assertEqual(PushDelivery.objects.filter(kind='campaign').get().device_id, opted_in.pk)
        order_delivery = self.enqueue()
        scheduled = campaign(actor, scheduled_at=timezone.now() + timedelta(days=1))
        publish_campaign(scheduled.pk, actor)
        due = set(due_deliveries(timezone.now()).values_list('pk', flat=True))
        self.assertIn(order_delivery.pk, due)
        self.assertFalse(PushDelivery.objects.filter(campaign=scheduled, pk__in=due).exists())
        self.assertEqual(deliver_pending(sender=self.sender), 2)
        item.refresh_from_db()
        scheduled.refresh_from_db()
        self.assertEqual((item.status, scheduled.status), ('completed', 'scheduled'))
        self.assertEqual(set(PushDelivery.objects.exclude(campaign=scheduled).values_list('status', flat=True)), {'accepted'})

    def test_campaign_still_requires_marketing_consent(self):
        actor = operator()
        item = campaign(actor)
        PushDelivery.objects.create(campaign=item, device=self.device, user=self.user, requested_by=actor,
                                    expected_scope=self.device.registration_scope, language='ru', title='t', body='b',
                                    next_attempt_at=timezone.now())
        PushCampaign.objects.filter(pk=item.pk).update(status='queued')
        self.assert_skipped(PushDelivery.objects.get(campaign=item), 'device_ineligible')

    def test_database_rejects_rows_without_a_source(self):
        base = {'device': self.device, 'user': self.user, 'expected_scope': uuid.uuid4(), 'language': 'ru',
                'title': 't', 'body': 'b', 'next_attempt_at': timezone.now()}
        invalid = (
            {},
            {'kind': 'order_update', 'order': self.order, 'order_event': 'order_confirmed'},
            {'kind': 'order_update', 'order': self.order, 'dedupe_key': 'x', 'campaign': campaign(operator())},
            {'kind': 'order_update', 'order': self.order, 'dedupe_key': 'y'},
            {'kind': 'other', 'order': self.order, 'order_event': 'order_confirmed', 'dedupe_key': 'z'},
        )
        for values in invalid:
            with self.subTest(values=sorted(values)), self.assertRaises(IntegrityError), transaction.atomic():
                PushDelivery.objects.create(**base, **values)


@override_settings(**PUSH_SETTINGS)
class OrderUpdateAdminTests(TestCase):
    def test_order_updates_are_listed_read_only_without_recipient_name(self):
        actor = operator()
        actor.is_superuser = True
        actor.save()
        user = shopper()
        device(user)
        order = purchase(user)
        Order.objects.filter(pk=order.pk).update(full_name='Synthetic Private Name')
        enqueue_order_update(order, 'payment_paid')
        delivery = PushDelivery.objects.get()
        self.client.force_login(actor)
        changelist = reverse('admin:notifications_pushdelivery_changelist')
        response = self.client.get(changelist, {'kind__exact': 'order_update'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_code)
        self.assertNotContains(response, 'Synthetic Private Name')
        self.assertEqual(self.client.get(changelist, {'q': order.order_code}).status_code, 200)
        detail = self.client.get(reverse('admin:notifications_pushdelivery_change', args=[delivery.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, order.order_code)
        self.assertNotContains(detail, 'Synthetic Private Name')
        self.assertNotContains(detail, delivery.dedupe_key)
        self.assertNotContains(detail, 'type="submit" value="Сохранить"')
