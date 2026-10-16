from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from firebase_admin import exceptions, messaging
from google.auth.exceptions import DefaultCredentialsError

from notifications.clients.firebase import FirebaseSender
from notifications.tests.fixtures import PUSH_SETTINGS


@override_settings(**PUSH_SETTINGS)
class FirebaseSenderTests(SimpleTestCase):
    def setUp(self):
        self.delivery = SimpleNamespace(pk='synthetic-delivery', kind='campaign', campaign_id='synthetic-campaign', order_id=None,
            expected_scope='synthetic-scope', title='Synthetic title', body='Synthetic body',
            target_url='https://bodysteel.uz/app/catalog')

    @patch('notifications.clients.firebase.firebase_admin.get_app')
    @patch('notifications.clients.firebase.messaging.send')
    def test_native_payloads_are_alerts_with_stable_identity_and_bounded_ttl(self, send, app):
        send.return_value = 'projects/synthetic/messages/synthetic'
        result = FirebaseSender().send('synthetic-token', self.delivery)
        self.assertEqual(result.outcome, 'accepted')
        message = send.call_args.args[0]
        self.assertEqual(message.android.ttl, timedelta(days=1))
        self.assertEqual(message.android.notification.channel_id, 'bodysteel_notifications')
        self.assertEqual(message.android.notification.tag, str(self.delivery.pk))
        self.assertEqual(message.android.collapse_key, 'synthetic-campaign')
        self.assertEqual(message.apns.headers['apns-collapse-id'], str(self.delivery.pk))
        self.assertEqual(message.apns.headers['apns-push-type'], 'alert')
        self.assertEqual(message.apns.payload.aps.sound, 'default')
        self.assertEqual(message.notification.title, self.delivery.title)
        self.assertEqual(set(message.data), {'notification_id', 'scope', 'url'})
        self.assertEqual(message.data['scope'], self.delivery.expected_scope)

    @patch('notifications.clients.firebase.firebase_admin.get_app')
    @patch('notifications.clients.firebase.messaging.send')
    def test_order_updates_replace_previous_alert_of_the_same_order(self, send, app):
        send.return_value = 'projects/synthetic/messages/synthetic'
        delivery = SimpleNamespace(**{**vars(self.delivery), 'kind': 'order_update', 'campaign_id': None, 'order_id': 42,
                                      'target_url': 'https://bodysteel.uz/app/orders'})
        FirebaseSender().send('synthetic-token', delivery)
        message = send.call_args.args[0]
        self.assertEqual(message.android.collapse_key, 'order-42')
        self.assertEqual(message.android.notification.tag, 'order-42')
        self.assertEqual(message.apns.headers['apns-collapse-id'], 'order-42')
        self.assertEqual(set(message.data), {'notification_id', 'scope', 'url'})
        self.assertEqual(message.data['url'], 'https://bodysteel.uz/app/orders')

    @patch('notifications.clients.firebase.firebase_admin.get_app')
    @patch('notifications.clients.firebase.messaging.send')
    def test_provider_failures_use_private_stable_codes(self, send, app):
        for error, outcome, code in [
            (messaging.UnregisteredError('private'), 'invalid_token', 'unregistered'),
            (messaging.QuotaExceededError('private'), 'retry', 'quota_exceeded'),
            (exceptions.UnavailableError('private'), 'retry', 'provider_unavailable'),
            (exceptions.UnauthenticatedError('private'), 'failed', 'provider_credentials'),
            (messaging.SenderIdMismatchError('private'), 'failed', 'provider_rejected'),
        ]:
            with self.subTest(code=code):
                send.side_effect = error
                result = FirebaseSender().send('synthetic-token', self.delivery)
                self.assertEqual((result.outcome, result.code), (outcome, code))
                self.assertNotIn('private', repr(result))

    @patch('notifications.clients.firebase.firebase_admin.initialize_app', side_effect=DefaultCredentialsError('private'))
    @patch('notifications.clients.firebase.firebase_admin.get_app', side_effect=ValueError())
    def test_absent_server_credentials_never_claim_delivery(self, app, initialize):
        result = FirebaseSender().send('synthetic-token', self.delivery)
        self.assertEqual((result.outcome, result.code), ('failed', 'provider_credentials'))
