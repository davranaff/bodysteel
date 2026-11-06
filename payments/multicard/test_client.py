import json

import httpx
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from payments.multicard.client import MulticardClient, MulticardRejected, MulticardUnavailable
from payments.multicard.configuration import MulticardNotConfigured, require_configuration
from payments.multicard.fixtures import INVOICE_UUID, MULTICARD_SETTINGS, SECRET


def invoice_data(**overrides):
    return {
        'uuid': INVOICE_UUID,
        'checkout_url': 'https://dev-checkout.multicard.uz/invoice/{}'.format(INVOICE_UUID),
        'payment': {'status': 'draft', 'uuid': INVOICE_UUID},
        **overrides,
    }


def client_for(handler):
    return MulticardClient(require_configuration(), httpx.Client(transport=httpx.MockTransport(handler)))


@override_settings(**MULTICARD_SETTINGS)
class MulticardClientTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_token_is_requested_once_and_reused_for_its_lifetime(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path == '/auth':
                return httpx.Response(200, json={'token': 'header.payload.sig', 'role': 'dev', 'expiry': '2099-01-01 10:00:00'})
            return httpx.Response(200, json={'success': True, 'data': invoice_data()})

        client = client_for(handler)
        client.create_invoice({'amount': 100})
        client.get_invoice(INVOICE_UUID)

        self.assertEqual([request.url.path for request in requests], [
            '/auth', '/payment/invoice', '/payment/invoice/{}'.format(INVOICE_UUID),
        ])
        self.assertEqual(json.loads(requests[0].content), {'application_id': 'rhmt_test', 'secret': SECRET})
        self.assertEqual(requests[1].headers['Authorization'], 'Bearer header.payload.sig')
        self.assertEqual(requests[1].method, 'POST')
        self.assertEqual(json.loads(requests[1].content), {'amount': 100})

    def test_expired_token_is_refreshed_once_on_401(self):
        tokens = iter(['first.token.value', 'second.token.value'])
        seen = []

        def handler(request):
            if request.url.path == '/auth':
                return httpx.Response(200, json={'token': next(tokens), 'role': 'dev', 'expiry': '2099-01-01 10:00:00'})
            seen.append(request.headers['Authorization'])
            if len(seen) == 1:
                return httpx.Response(401, json={'success': False})
            return httpx.Response(200, json={'success': True, 'data': invoice_data()})

        invoice = client_for(handler).get_invoice(INVOICE_UUID)
        self.assertEqual(invoice.uuid, INVOICE_UUID)
        self.assertEqual(seen, ['Bearer first.token.value', 'Bearer second.token.value'])

    def test_invoice_parsing_maps_payment_status(self):
        def handler(request):
            if request.url.path == '/auth':
                return httpx.Response(200, json={'token': 'header.payload.sig', 'role': 'dev', 'expiry': 'bad'})
            return httpx.Response(200, json={'success': True, 'data': invoice_data(payment={
                'status': 'success', 'uuid': 'e60d8ebc-b9fe-11ef-b159-005056b4367d',
            })})

        invoice = client_for(handler).get_invoice(INVOICE_UUID)
        self.assertEqual(invoice.payment_status, 'success')
        self.assertEqual(invoice.payment_uuid, 'e60d8ebc-b9fe-11ef-b159-005056b4367d')

    def test_business_errors_and_transport_failures_are_distinguished(self):
        def rejected(request):
            if request.url.path == '/auth':
                return httpx.Response(200, json={'token': 'header.payload.sig', 'role': 'dev', 'expiry': 'x'})
            return httpx.Response(400, json={'success': False, 'error': {'code': 'ERROR_FIELDS', 'details': 'x'}})

        with self.assertRaises(MulticardRejected) as error:
            client_for(rejected).create_invoice({})
        self.assertEqual(error.exception.code, 'ERROR_FIELDS')

        def broken(request):
            raise httpx.ConnectError('down')

        with self.assertRaises(MulticardUnavailable):
            client_for(broken).create_invoice({})

        def redirect(request):
            return httpx.Response(302, headers={'Location': 'https://evil.test/'})

        with self.assertRaises(MulticardUnavailable):
            client_for(redirect).create_invoice({})

    def test_rejected_credentials_do_not_echo_the_secret(self):
        def handler(request):
            return httpx.Response(400, json={'errors': [{'message': [{'message': 'Invalid Credentials'}]}]})

        with self.assertRaises(MulticardUnavailable) as error:
            client_for(handler).create_invoice({})
        self.assertNotIn(SECRET, str(error.exception))
        self.assertNotIn(SECRET, repr(require_configuration()))

    def test_non_https_checkout_url_is_refused(self):
        def handler(request):
            if request.url.path == '/auth':
                return httpx.Response(200, json={'token': 'header.payload.sig', 'role': 'dev', 'expiry': 'x'})
            return httpx.Response(200, json={'success': True, 'data': invoice_data(checkout_url='http://x.test/')})

        with self.assertRaises(MulticardUnavailable):
            client_for(handler).create_invoice({})


class MulticardConfigurationTests(SimpleTestCase):
    @override_settings(**{**MULTICARD_SETTINGS, 'MULTICARD_ENABLED': False})
    def test_disabled_fails_closed(self):
        with self.assertRaises(MulticardNotConfigured):
            require_configuration()

    @override_settings(**{**MULTICARD_SETTINGS, 'MULTICARD_SECRET': ''})
    def test_missing_secret_fails_closed(self):
        with self.assertRaises(MulticardNotConfigured):
            require_configuration()

    @override_settings(**{**MULTICARD_SETTINGS, 'MULTICARD_BASE_URL': 'http://dev-mesh.multicard.uz'})
    def test_plain_http_gateway_is_refused(self):
        with self.assertRaises(MulticardNotConfigured):
            require_configuration()

    @override_settings(**{**MULTICARD_SETTINGS, 'MULTICARD_CALLBACK_URL': ''})
    def test_missing_callback_url_fails_closed(self):
        with self.assertRaises(MulticardNotConfigured):
            require_configuration()
