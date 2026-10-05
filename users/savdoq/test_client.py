import json
from datetime import timedelta

import httpx
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from users.savdoq.client import SavdoqRefused, SavdoqShopperClient, SavdoqUnavailable
from users.savdoq.configuration import (
    SavdoqShopperConfigurationError,
    require_configuration,
)
from users.savdoq.test_api import SAVDOQ_SETTINGS, SERVICE_TOKEN


SUBJECT = 'f' * 64


def client_for(handler):
    return SavdoqShopperClient(
        require_configuration(),
        httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False),
    )


def session_body(**overrides):
    return {
        'accessToken': 'header.payload.signature',
        'tokenType': 'Bearer',
        'expiresAt': (timezone.now() + timedelta(minutes=15)).isoformat(),
        'sessionId': '08e133c5-f6e8-4ed1-a0c0-4c3a5797807c',
        'persistent': True,
        'shopperAuthenticated': True,
        **overrides,
    }


@override_settings(**SAVDOQ_SETTINGS)
class SavdoqShopperClientTests(SimpleTestCase):
    def test_issue_sends_the_scoped_service_request(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(201, json=session_body())

        issued = client_for(handler).issue(SUBJECT, 'uz')
        self.assertEqual(issued.access_token, 'header.payload.signature')
        request = requests[0]
        self.assertEqual(request.method, 'POST')
        self.assertEqual(
            str(request.url), 'https://rag.example.test/api/v1/integrations/widget-shopper-sessions',
        )
        self.assertEqual(request.headers['Authorization'], f'Bearer {SERVICE_TOKEN}')
        self.assertEqual(request.headers['Accept-Language'], 'uz')
        self.assertEqual(json.loads(request.content), {
            'publicKey': 'wpk_' + 'a' * 32,
            'origin': 'https://shop.example.test',
            'issuer': 'bodysteel',
            'subjectHash': SUBJECT,
        })

    def test_refusals_keep_a_bounded_retry_after(self):
        cases = ((403, {}, 403, None), (429, {'Retry-After': '9'}, 429, 9),
                 (429, {'Retry-After': 'tomorrow'}, 429, None))
        for status, headers, expected, retry_after in cases:
            client = client_for(lambda request: httpx.Response(status, headers=headers))
            with self.assertRaises(SavdoqRefused) as caught:
                client.issue(SUBJECT, 'ru')
            self.assertEqual((caught.exception.status, caught.exception.retry_after),
                             (expected, retry_after))

    def test_unusable_responses_are_outages(self):
        expired = (timezone.now() + timedelta(seconds=5)).isoformat()
        responses = (
            httpx.Response(500),
            httpx.Response(302, headers={'Location': 'https://evil.example.test'}),
            httpx.Response(201, content=b'not json'),
            httpx.Response(201, json=session_body(tokenType='Basic')),
            httpx.Response(201, json=session_body(accessToken='has spaces')),
            httpx.Response(201, json=session_body(sessionId='not-a-uuid')),
            httpx.Response(201, json=session_body(shopperAuthenticated=False)),
            httpx.Response(201, json=session_body(expiresAt=expired)),
            httpx.Response(201, content=b'x' * (9 * 1024)),
        )
        for response in responses:
            with self.assertRaises(SavdoqUnavailable):
                client_for(lambda request, response=response: response).issue(SUBJECT, 'ru')

    def test_transport_errors_are_outages_without_details(self):
        def handler(request):
            raise httpx.ConnectError('private-upstream-detail', request=request)

        with self.assertRaises(SavdoqUnavailable) as caught:
            client_for(handler).issue(SUBJECT, 'ru')
        self.assertNotIn('private-upstream-detail', str(caught.exception))

    def test_revoke_uses_delete_and_requires_success(self):
        methods = []

        def handler(request):
            methods.append(request.method)
            return httpx.Response(204)

        client_for(handler).revoke(SUBJECT)
        self.assertEqual(methods, ['DELETE'])
        with self.assertRaises(SavdoqUnavailable):
            client_for(lambda request: httpx.Response(503)).revoke(SUBJECT)


class SavdoqShopperConfigurationTests(SimpleTestCase):
    def test_rejects_partial_or_unsafe_configuration(self):
        invalid = (
            {'SAVDOQ_API_ORIGIN': 'http://rag.example.test'},
            {'SAVDOQ_API_ORIGIN': 'https://rag.example.test/path'},
            {'SAVDOQ_STOREFRONT_ORIGIN': 'https://user:pass@shop.example.test'},
            {'SAVDOQ_WIDGET_PUBLIC_KEY': 'wpk_short'},
            {'SAVDOQ_SHOPPER_SERVICE_TOKEN': 'short'},
            {'SAVDOQ_SHOPPER_IDENTITY_KEY': SERVICE_TOKEN},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides), override_settings(
                **{**SAVDOQ_SETTINGS, **overrides},
            ):
                with self.assertRaises(SavdoqShopperConfigurationError):
                    require_configuration()
