import json
from datetime import datetime, timezone
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from customer_telegram.models import CustomerTelegramChat, CustomerTelegramUpdate
from customer_telegram.tests.base import TELEGRAM_SETTINGS


@override_settings(**TELEGRAM_SETTINGS)
class CustomerTelegramWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = '/telegram/customer/webhook/'
        self.headers = {
            'HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN': TELEGRAM_SETTINGS['CUSTOMER_TELEGRAM_WEBHOOK_SECRET'],
        }

    def test_boundary_rejects_wrong_method_secret_media_and_body(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.post(self.url, data='{}', content_type='application/json').status_code, 403)
        self.assertEqual(self.client.post(
            self.url, data='{}', content_type='text/plain', **self.headers,
        ).status_code, 415)
        self.assertEqual(self.client.post(
            self.url, data='{', content_type='application/json', **self.headers,
        ).status_code, 400)
        self.assertEqual(self.client.post(
            self.url,
            data=json.dumps({'update_id': 1 << 80, 'message': {}}),
            content_type='application/json',
            **self.headers,
        ).status_code, 400)
        self.assertEqual(self.client.post(
            self.url, data=json.dumps({'update_id': 1}), content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='wrong-secret-value-00000000000000',
        ).status_code, 403)
        self.assertEqual(self.client.post(
            self.url,
            data='x' * (64 * 1024 + 1),
            content_type='application/json',
            **self.headers,
        ).status_code, 413)

    @patch('customer_telegram.webhook.handle_update')
    def test_update_is_idempotent_without_raw_payload_persistence(self, handle):
        payload = self.message_update(77)
        first = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json', **self.headers,
        )
        second = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json', **self.headers,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(handle.call_count, 1)
        record = CustomerTelegramUpdate.objects.get(update_id=77)
        self.assertEqual(record.status, 'processed')
        self.assertFalse(any(field.name in {'payload', 'body', 'raw_update'} for field in record._meta.fields))

    def test_unsupported_update_is_ignored_without_storage(self):
        response = self.client.post(
            self.url,
            data=json.dumps({'update_id': 88, 'channel_post': {}}),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CustomerTelegramUpdate.objects.filter(update_id=88).exists())

    def test_group_chat_is_processed_safely_without_creating_customer(self):
        payload = self.message_update(89)
        payload['message']['chat'] = {'id': -1005001, 'type': 'group'}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json', **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CustomerTelegramChat.objects.exists())
        self.assertEqual(CustomerTelegramUpdate.objects.get(update_id=89).status, 'processed')

    @patch('customer_telegram.webhook.handle_update', side_effect=RuntimeError('safe failure'))
    def test_internal_failure_is_acknowledged_without_retry_storm(self, _handle):
        with self.assertLogs('customer_telegram.webhook', level='ERROR'):
            response = self.client.post(
                self.url,
                data=json.dumps(self.message_update(90)),
                content_type='application/json',
                **self.headers,
            )
        self.assertEqual(response.status_code, 200)
        record = CustomerTelegramUpdate.objects.get(update_id=90)
        self.assertEqual(record.failure_code, 'processing_error')

    @patch('customer_telegram.webhook.handle_update')
    @patch('customer_telegram.webhook.timezone.now')
    def test_per_telegram_user_rate_limit_is_hashed_and_acknowledged(self, clock, handle):
        clock.return_value = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        for update_id in range(1_000, 1_061):
            response = self.client.post(
                self.url,
                data=json.dumps(self.message_update(update_id)),
                content_type='application/json',
                **self.headers,
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(handle.call_count, 60)
        self.assertEqual(
            CustomerTelegramUpdate.objects.get(update_id=1_060).failure_code,
            'rate_limited',
        )

    @staticmethod
    def message_update(update_id):
        return {
            'update_id': update_id,
            'message': {
                'message_id': 1,
                'from': {'id': 1001, 'is_bot': False},
                'chat': {'id': 1001, 'type': 'private'},
                'text': '/start',
            },
        }
