import json

import httpx
from django.test import SimpleTestCase, override_settings

from customer_telegram.bot_api import CustomerTelegramApi, DeliveryStatus
from customer_telegram.tests.base import TELEGRAM_SETTINGS


@override_settings(**TELEGRAM_SETTINGS)
class CustomerTelegramBotApiTests(SimpleTestCase):
    def test_send_message_uses_fixed_api_and_strict_success(self):
        captured = {}

        def handler(request):
            captured['method'] = request.method
            captured['url'] = str(request.url)
            captured['payload'] = json.loads(request.content)
            return httpx.Response(200, json={'ok': True, 'result': {'message_id': 91}})

        result = self.api(handler).send_message(1001, '<b>safe</b>')
        self.assertEqual(result.status, DeliveryStatus.SENT)
        self.assertEqual(result.message_id, 91)
        self.assertEqual(captured['method'], 'POST')
        self.assertEqual(
            captured['url'],
            'https://api.telegram.org/bot{}/sendMessage'.format(
                TELEGRAM_SETTINGS['CUSTOMER_TELEGRAM_BOT_TOKEN'],
            ),
        )
        self.assertEqual(captured['payload']['chat_id'], 1001)

    def test_adapter_classifies_bounded_failures_without_raw_descriptions(self):
        cases = (
            (httpx.Response(403, json={'ok': False, 'description': 'blocked'}), DeliveryStatus.BLOCKED),
            (httpx.Response(429, json={
                'ok': False, 'description': 'slow', 'parameters': {'retry_after': 45},
            }), DeliveryStatus.RATE_LIMITED),
            (httpx.Response(500, json={'ok': False}), DeliveryStatus.UNKNOWN),
            (httpx.Response(400, json={'ok': False, 'description': 'bad'}), DeliveryStatus.FAILED),
            (httpx.Response(200, content=b'not-json'), DeliveryStatus.UNKNOWN),
            (httpx.Response(200, content=b'{' + b'A' * (64 * 1024) + b'}'), DeliveryStatus.UNKNOWN),
        )
        for response, expected in cases:
            with self.subTest(expected=expected, status=response.status_code):
                result = self.api(lambda _request, value=response: value).send_message(1002, 'safe')
                self.assertEqual(result.status, expected)
                self.assertFalse(hasattr(result, 'description'))
        limited = self.api(lambda _request: cases[1][0]).send_message(1002, 'safe')
        self.assertEqual(limited.retry_after, 45)

    def test_network_failure_is_unknown(self):
        def handler(request):
            raise httpx.ConnectTimeout('timeout', request=request)

        self.assertEqual(
            self.api(handler).send_message(1003, 'safe').status,
            DeliveryStatus.UNKNOWN,
        )

    @staticmethod
    def api(handler):
        return CustomerTelegramApi(client=httpx.Client(transport=httpx.MockTransport(handler)))
