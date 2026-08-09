import json
import unittest

import httpx

from users.auth.configuration import EskizConfiguration
from users.auth.eskiz import EskizSmsGateway
from users.auth.ports import SmsDeliveryResult


CONFIGURATION = EskizConfiguration(
    email='provider@example.test',
    password='provider-password',
    sender='4546',
    template='BodySteel code: {code}',
)


class FakeHttpClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeStream(*outcome)


class FakeStream:
    def __init__(self, status, content):
        self.response = FakeResponse(status, content)

    def __enter__(self):
        return self.response

    def __exit__(self, *args):
        return False


class FakeResponse:
    def __init__(self, status, content):
        self.status_code = status
        self.content = content

    def iter_bytes(self):
        yield self.content


class EskizGatewayTests(unittest.TestCase):
    def test_authenticates_and_maps_canonical_phone_to_provider(self):
        client = FakeHttpClient([
            (200, json.dumps({'data': {'token': 'jwt-token'}}).encode()),
            (200, b'{}'),
        ])

        result = EskizSmsGateway(CONFIGURATION, client).send_otp('+998901234567', '482901')

        self.assertIs(result, SmsDeliveryResult.SENT)
        fields = client.calls[1][2]['files']
        self.assertEqual(fields['mobile_phone'], (None, '998901234567'))
        self.assertEqual(fields['message'], (None, 'BodySteel code: 482901'))
        self.assertEqual(client.calls[1][2]['headers']['Authorization'], 'Bearer jwt-token')

    def test_reauthenticates_once_only_after_explicit_unauthorized_response(self):
        client = FakeHttpClient([
            (200, json.dumps({'data': {'token': 'old'}}).encode()),
            (401, b'{}'),
            (200, json.dumps({'data': {'token': 'new'}}).encode()),
            (200, b'{}'),
        ])

        result = EskizSmsGateway(CONFIGURATION, client).send_otp('+998901234567', '482901')

        self.assertIs(result, SmsDeliveryResult.SENT)
        self.assertEqual(len(client.calls), 4)

    def test_transport_or_oversized_send_response_has_unknown_delivery(self):
        login = (200, json.dumps({'data': {'token': 'jwt-token'}}).encode())
        timeout_client = FakeHttpClient([login, httpx.ReadTimeout('timeout')])
        oversized_client = FakeHttpClient([login, (200, b'x' * (64 * 1024 + 1))])

        self.assertIs(
            EskizSmsGateway(CONFIGURATION, timeout_client).send_otp('+998901234567', '482901'),
            SmsDeliveryResult.UNKNOWN,
        )
        self.assertIs(
            EskizSmsGateway(CONFIGURATION, oversized_client).send_otp('+998901234567', '482901'),
            SmsDeliveryResult.UNKNOWN,
        )
