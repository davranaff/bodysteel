from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from notifications.clients.firebase import SendResult
from notifications.configuration import PushNotConfigured
from notifications.models import PushCampaign, PushDelivery
from notifications.services.campaigns import cancel_campaign, preview_audience, publish_campaign, queue_test, save_draft
from notifications.services.delivery import LEASE_SECONDS, deliver_pending
from notifications.services.devices import register_device
from notifications.tests.fixtures import PUSH_SETTINGS, FakeSender, campaign, device, device_values, operator, shopper
from rest_framework.authtoken.models import Token


@override_settings(**PUSH_SETTINGS)
class DeliveryTests(TestCase):
    def setUp(self):
        self.actor = operator()
        self.user = shopper()
        self.device = device(self.user)
        self.campaign = campaign(self.actor)
        self.sender = FakeSender()

    def publish(self):
        publish_campaign(self.campaign.pk, self.actor)
        return PushDelivery.objects.get(is_test=False)

    def test_publish_is_atomic_and_idempotent(self):
        self.assertEqual(preview_audience(self.campaign).devices, 1)
        self.assertTrue(publish_campaign(self.campaign.pk, self.actor, expected_size=1))
        self.assertFalse(publish_campaign(self.campaign.pk, self.actor))
        self.assertEqual(PushDelivery.objects.count(), 1)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.user_count, 1)
        with self.assertRaises(ValidationError):
            save_draft(self.campaign, self.actor)

    def test_no_permission_no_configuration_or_changed_count_never_queues(self):
        with self.assertRaises(PermissionDenied):
            publish_campaign(self.campaign.pk, self.user)
        with override_settings(PUSH_ENABLED=False), self.assertRaises(PushNotConfigured):
            publish_campaign(self.campaign.pk, self.actor)
        with self.assertRaises(ValidationError):
            publish_campaign(self.campaign.pk, self.actor, expected_size=2)
        self.assertFalse(PushDelivery.objects.exists())

    def test_content_and_language_are_snapshots(self):
        self.device.language = 'uz'
        self.device.save()
        delivery = self.publish()
        PushCampaign.objects.filter(pk=self.campaign.pk).update(body_uz='Changed')
        self.assertEqual(delivery.body, 'UZ text')
        self.assertEqual(deliver_pending(sender=self.sender), 1)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'accepted')
        self.assertEqual(deliver_pending(sender=self.sender), 0)
        self.assertEqual(len(self.sender.calls), 1)

    def test_consent_withdrawal_and_owner_change_skip_before_provider(self):
        delivery = self.publish()
        self.device.marketing_opt_in = False
        self.device.save()
        deliver_pending(sender=self.sender)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'skipped')
        self.assertEqual(self.sender.calls, [])

    def test_session_rotation_skips_old_installation(self):
        delivery = self.publish()
        Token.objects.filter(user=self.user).delete()
        Token.objects.create(user=self.user)
        deliver_pending(sender=self.sender)
        delivery.refresh_from_db()
        self.assertEqual(delivery.failure_code, 'session_revoked')
        self.assertEqual(self.sender.calls, [])

    def test_transferred_device_cannot_receive_prior_owner_campaign(self):
        delivery = self.publish()
        other = shopper(2)
        credential = Token.objects.create(user=other)
        register_device(other, credential, self.device.installation_id, device_values(), 'ru')
        deliver_pending(sender=self.sender)
        delivery.refresh_from_db()
        self.assertEqual(delivery.failure_code, 'device_ineligible')
        self.assertEqual(self.sender.calls, [])

    def test_unknown_token_does_not_deactivate_refreshed_token(self):
        delivery = self.publish()
        def refresh(_):
            register_device(self.user, Token.objects.get(user=self.user), self.device.installation_id,
                            device_values(token='synthetic-new-fcm-token-0000000002'), 'ru')
        sender = FakeSender([SendResult('invalid_token', code='unregistered')], callback=refresh)
        deliver_pending(sender=sender)
        self.device.refresh_from_db()
        self.assertTrue(self.device.is_active)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'failed')

    def test_transient_failure_backoff_then_acceptance(self):
        delivery = self.publish()
        now = timezone.now()
        sender = FakeSender([SendResult('retry', code='quota', retry_after=120), SendResult('accepted')])
        deliver_pending(sender=sender, now=now)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'retry')
        self.assertGreaterEqual(delivery.next_attempt_at, now + timedelta(seconds=120))
        self.assertEqual(deliver_pending(sender=sender, now=now), 0)
        deliver_pending(sender=sender, now=delivery.next_attempt_at)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'accepted')
        self.assertEqual(delivery.attempt_count, 2)

    def test_cancel_and_permission_revocation_stop_pending_send(self):
        self.publish()
        self.assertTrue(cancel_campaign(self.campaign.pk, self.actor))
        self.assertEqual(deliver_pending(sender=self.sender), 0)
        self.assertEqual(PushDelivery.objects.get().failure_code, 'campaign_cancelled')

    def test_publisher_permission_is_rechecked(self):
        delivery = self.publish()
        self.actor.is_staff = False
        self.actor.save()
        deliver_pending(sender=self.sender)
        delivery.refresh_from_db()
        self.assertEqual(delivery.failure_code, 'publisher_unavailable')
        self.assertEqual(self.sender.calls, [])

    def test_lease_and_attempt_limit_are_bounded(self):
        delivery = self.publish()
        now = timezone.now()
        PushDelivery.objects.filter(pk=delivery.pk).update(status='sending', attempt_count=5,
            locked_at=now - timedelta(seconds=LEASE_SECONDS + 1))
        self.assertEqual(deliver_pending(sender=self.sender, now=now), 0)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'failed')
        self.assertEqual(delivery.failure_code, 'attempts_exhausted')

    def test_test_is_own_device_only_and_does_not_wait_for_future_campaign(self):
        self.campaign.scheduled_at = timezone.now() + timedelta(days=1)
        self.campaign.save()
        with self.assertRaises(ValidationError):
            queue_test(self.campaign.pk, self.device.pk, self.actor)
        own = device(self.actor, marketing_opt_in=False)
        identifier = queue_test(self.campaign.pk, own.pk, self.actor)
        self.assertEqual(deliver_pending(sender=self.sender), 1)
        self.assertEqual(PushDelivery.objects.get(pk=identifier).status, 'accepted')
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'draft')
