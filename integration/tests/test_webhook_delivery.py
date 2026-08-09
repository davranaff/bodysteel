import hashlib
import hmac
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.core.management import call_command
from django.test import TestCase, override_settings

from integration.checks import integration_configuration_checks
from integration.models import IntegrationWebhookEvent
from integration.tests.fixtures import WEBHOOK_SETTINGS
from integration.webhooks.delivery import WebhookDeliveryService
from integration.webhooks.events import enqueue_product_events
from integration.webhooks.signing import sign_webhook
from integration.webhooks.transport import (
    WebhookTransportError,
    WebhookTransportResponse,
)


class FakeTransport:
    def __init__(self, response=None, error=False):
        self.response = response or WebhookTransportResponse(202)
        self.error = error
        self.calls = []

    def send(self, url, body, headers):
        self.calls.append((url, body, headers))
        if self.error:
            raise WebhookTransportError('failed')
        return self.response


@override_settings(**WEBHOOK_SETTINGS)
class WebhookDeliveryTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 8, 12, 0, tzinfo=datetime_timezone.utc)

    def event(self):
        enqueue_product_events('product.updated', ('1015',), self.now)
        event = IntegrationWebhookEvent.objects.get()
        IntegrationWebhookEvent.objects.filter(pk=event.pk).update(next_attempt_at=self.now)
        return event

    def service(self, transport):
        return WebhookDeliveryService(
            transport,
            clock=lambda: self.now,
            jitter=lambda base_delay: 0,
        )

    def test_signature_matches_exact_raw_body_and_success_is_terminal(self):
        event = self.event()
        transport = FakeTransport()

        summary = self.service(transport).deliver_batch()

        event.refresh_from_db()
        self.assertEqual(summary.delivered, 1)
        self.assertEqual(event.status, 'delivered')
        url, body, headers = transport.calls[0]
        timestamp = str(int(self.now.timestamp()))
        expected = hmac.new(
            WEBHOOK_SETTINGS['SAVDOQ_WEBHOOK_SECRET'].encode(),
            '{}.{}'.format(timestamp, body).encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(url, WEBHOOK_SETTINGS['SAVDOQ_WEBHOOK_URL'])
        self.assertEqual(headers['X-Webhook-Id'], event.event_id)
        self.assertEqual(headers['X-Webhook-Signature'], 'v1={}'.format(expected))
        self.assertNotEqual(sign_webhook(WEBHOOK_SETTINGS['SAVDOQ_WEBHOOK_SECRET'], timestamp, body + ' '), headers['X-Webhook-Signature'])

    def test_retry_after_is_honored_and_permanent_http_stops(self):
        event = self.event()
        retry = FakeTransport(WebhookTransportResponse(429, retry_after='600'))

        summary = self.service(retry).deliver_batch()

        event.refresh_from_db()
        self.assertEqual(summary.retried, 1)
        self.assertEqual(event.status, 'retry')
        self.assertEqual(event.next_attempt_at, self.now + timedelta(seconds=600))

        event.next_attempt_at = self.now
        event.save(update_fields=('next_attempt_at',))
        failed = self.service(FakeTransport(WebhookTransportResponse(400))).deliver_batch()
        event.refresh_from_db()
        self.assertEqual(failed.failed, 1)
        self.assertEqual(event.status, 'failed')
        self.assertEqual(event.failure_code, 'permanent_http')

    def test_network_retry_is_bounded_and_stale_lease_resumes(self):
        event = self.event()
        event.status = 'delivering'
        event.locked_at = self.now - timedelta(minutes=6)
        event.attempt_count = 5
        event.save(update_fields=('status', 'locked_at', 'attempt_count'))

        summary = self.service(FakeTransport(error=True)).deliver_batch()

        event.refresh_from_db()
        self.assertEqual(summary.failed, 1)
        self.assertEqual(event.status, 'failed')
        self.assertEqual(event.attempt_count, 6)
        self.assertEqual(event.failure_code, 'retry_exhausted')

    @override_settings(SAVDOQ_WEBHOOK_URL='http://127.0.0.1/internal')
    def test_unsafe_webhook_configuration_fails_system_check(self):
        issues = integration_configuration_checks(None)
        self.assertEqual([issue.id for issue in issues], ['integration.E001'])

    def test_retention_deletes_only_old_terminal_events(self):
        delivered = self.event()
        delivered.status = 'delivered'
        delivered.delivered_at = self.now - timedelta(days=31)
        delivered.save(update_fields=('status', 'delivered_at'))
        enqueue_product_events('product.updated', ('1016',), self.now)
        pending = IntegrationWebhookEvent.objects.exclude(pk=delivered.pk).get()

        call_command('purge_integration_webhooks', verbosity=0)

        self.assertFalse(IntegrationWebhookEvent.objects.filter(pk=delivered.pk).exists())
        self.assertTrue(IntegrationWebhookEvent.objects.filter(pk=pending.pk).exists())
