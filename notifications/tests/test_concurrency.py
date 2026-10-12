import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from rest_framework.authtoken.models import Token

from notifications.clients.firebase import SendResult
from notifications.models import PushDelivery, PushDevice
from notifications.services.campaigns import publish_campaign
from notifications.services.delivery import deliver_pending
from notifications.services.devices import register_device
from notifications.tests.fixtures import PUSH_SETTINGS, FakeSender, campaign, device, device_values, operator, shopper


def _connection(operation):
    close_old_connections()
    try:
        return operation()
    finally:
        close_old_connections()


@skipUnless(connection.vendor == 'postgresql', 'Row-lock verification requires PostgreSQL')
@override_settings(**PUSH_SETTINGS)
class PushConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = operator()
        self.user = shopper()
        self.device = device(self.user)
        self.campaign = campaign(self.actor)

    def test_simultaneous_publish_creates_one_snapshot(self):
        barrier = Barrier(2)
        def publish():
            barrier.wait(timeout=10)
            return publish_campaign(self.campaign.pk, self.actor)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: _connection(publish), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(PushDelivery.objects.count(), 1)

    def test_simultaneous_registration_is_one_installation(self):
        identifier = uuid.uuid4()
        credential = Token.objects.get(user=self.user)
        barrier = Barrier(2)
        def register():
            barrier.wait(timeout=10)
            return register_device(self.user, credential, identifier,
                device_values(token='synthetic-concurrent-registration-token'), 'ru')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: _connection(register), range(2)))
        self.assertEqual(results[0]['registration_scope'], results[1]['registration_scope'])
        self.assertEqual(PushDevice.objects.filter(installation_id=identifier).count(), 1)

    def test_second_worker_cannot_claim_an_inflight_delivery(self):
        publish_campaign(self.campaign.pk, self.actor)
        entered, release = Event(), Event()
        class BlockingSender:
            def send(self, token, delivery):
                entered.set()
                if not release.wait(timeout=10):
                    raise AssertionError('Second-worker check timed out')
                return SendResult('accepted')
        second = FakeSender()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(_connection, lambda: deliver_pending(sender=BlockingSender()))
            try:
                self.assertTrue(entered.wait(timeout=10))
                self.assertEqual(deliver_pending(sender=second), 0)
                self.assertEqual(second.calls, [])
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=10), 1)
        self.assertEqual(PushDelivery.objects.get().status, 'accepted')
