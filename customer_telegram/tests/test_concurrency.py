import queue
import threading
from unittest import skipUnless
from urllib.parse import parse_qs, urlsplit

from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from customer_telegram.links import open_link, start_account_link, start_registration
from customer_telegram.otp import process_contact
from customer_telegram.tests.base import FakeTelegramApi, TELEGRAM_SETTINGS
from users.models import User


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row-lock semantics required')
@override_settings(**TELEGRAM_SETTINGS)
class CustomerTelegramConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_deep_link_claim_has_exactly_one_owner(self):
        user = User.objects.create_user(
            username='claim-race', email='claim-race@example.test',
            phone='+998901234701', password='safe-password',
        )
        token = self.token(start_account_link(user, 'ru').telegram_url)
        results = self.concurrent([
            lambda: open_link(token, 7701, 7701).link is not None,
            lambda: open_link(token, 7702, 7702).link is not None,
        ])
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 1)

    def test_concurrent_contact_delivery_sends_exactly_one_otp(self):
        values = {
            'email': 'contact-race@example.test', 'phone': '+998901234702',
            'username': 'contact-race', 'first_name': 'Contact', 'last_name': 'Race',
        }
        token = self.token(start_registration(values, '192.0.2.70', 'ru').telegram_url)
        link = open_link(token, 7703, 7703).link
        apis = (FakeTelegramApi(), FakeTelegramApi())
        contact = {'user_id': 7703, 'phone_number': '+998901234702'}
        results = self.concurrent([
            lambda: process_contact(link.pk, 7703, 7703, contact, apis[0]).status,
            lambda: process_contact(link.pk, 7703, 7703, contact, apis[1]).status,
        ])
        self.assertEqual(results.count('delivered'), 1)
        self.assertEqual(sum(len(api.messages) for api in apis), 1)

    @staticmethod
    def token(url):
        return parse_qs(urlsplit(url).query)['start'][0]

    @staticmethod
    def concurrent(operations):
        barrier = threading.Barrier(len(operations))
        outcomes = queue.Queue()

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                outcomes.put(operation())
            finally:
                close_old_connections()

        threads = [threading.Thread(target=run, args=(operation,)) for operation in operations]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            if thread.is_alive():
                raise AssertionError('Concurrent Telegram test worker did not finish')
        return [outcomes.get_nowait() for _ in operations]
