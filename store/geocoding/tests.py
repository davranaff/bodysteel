from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.test import TestCase, override_settings

from store.geocoding.service import GEOCODE_IP
from users.auth.test_registration import SECURITY_SETTINGS


REVERSE_URL = '/api/v1/store/geocode/reverse/'
SEARCH_URL = '/api/v1/store/geocode/search/'
GEOCODER = 'https://geocoder.example.test'
REVERSE_BODY = {
    'name': 'Ляби-Хауз',
    'display_name': 'Ляби-Хауз, улица Накшбанди, Бухара, Узбекистан',
    'address': {'road': 'улица Накшбанди', 'house_number': '5', 'city': 'Бухара', 'country_code': 'uz'},
}
SEARCH_BODY = [
    {**REVERSE_BODY, 'lat': '39.7740', 'lon': '64.4198'},
    {'name': '', 'display_name': 'Ташкент, Узбекистан', 'address': {'city': 'Ташкент'},
     'lat': '41.3111', 'lon': '69.2797'},
    {'name': 'Outside', 'display_name': 'Moscow', 'lat': '55.75', 'lon': '37.61'},
]


@override_settings(**SECURITY_SETTINGS, GEOCODER_BASE_URL=GEOCODER + '/')
class GeocodeApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.requests = []
        self.reply = lambda request: httpx.Response(200, json=REVERSE_BODY)
        transport = httpx.MockTransport(self.handle)
        patcher = patch(
            'store.geocoding.nominatim.http_client',
            side_effect=lambda: httpx.Client(transport=transport, follow_redirects=False),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def handle(self, request):
        self.requests.append(request)
        return self.reply(request)

    def test_reverse_returns_label_and_address_and_sends_policy_headers(self):
        response = self.client.get(REVERSE_URL, {'lat': '39.7747231', 'lng': '64.4198412'}, HTTP_ACCEPT_LANGUAGE='uz')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'data': {
            'label': 'Ляби-Хауз', 'address': 'улица Накшбанди, 5, Бухара',
        }})
        self.assertEqual(response['Content-Language'], 'uz')
        request = self.requests[0]
        self.assertEqual(request.url.host, 'geocoder.example.test')
        self.assertEqual(request.url.path, '/reverse')
        self.assertEqual(request.url.params['lat'], '39.77472')
        self.assertEqual(request.url.params['lon'], '64.41984')
        self.assertEqual(request.url.params['accept-language'], 'uz')
        self.assertEqual(request.headers['User-Agent'], 'BODYSTEEL/1.0 (+https://bodysteel.uz)')

    def test_reverse_is_cached_by_rounded_coordinates_and_language(self):
        self.client.get(REVERSE_URL, {'lat': '39.774721', 'lng': '64.419841'})
        self.client.get(REVERSE_URL, {'lat': '39.774719', 'lng': '64.419839'})
        self.client.get(REVERSE_URL, {'lat': '39.774721', 'lng': '64.419841'}, HTTP_ACCEPT_LANGUAGE='uz')

        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0].url.params['accept-language'], 'ru')

    def test_reverse_without_a_place_returns_empty_strings(self):
        self.reply = lambda request: httpx.Response(200, json={'error': 'Unable to geocode'})

        response = self.client.get(REVERSE_URL, {'lat': '40', 'lng': '64'})

        self.assertEqual(response.json(), {'data': {'label': '', 'address': ''}})

    def test_reverse_validates_coordinates_and_query(self):
        cases = [
            ({'lat': '55.75', 'lng': '37.61'}, 'outside_service_area'),
            ({'lat': '0', 'lng': '0'}, 'outside_service_area'),
            ({'lat': 'nan', 'lng': '64.4'}, 'invalid_request'),
            ({'lat': 'abc', 'lng': '64.4'}, 'invalid_request'),
            ({'lat': '39.7'}, 'invalid_request'),
            ({'lat': '39.7', 'lng': '64.4', 'zoom': '3'}, 'invalid_request'),
        ]
        for params, code in cases:
            with self.subTest(params=params):
                response = self.client.get(REVERSE_URL, params)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error']['code'], code)
        self.assertEqual(self.requests, [])

    def test_search_is_restricted_to_uzbekistan_and_cached(self):
        self.reply = lambda request: httpx.Response(200, json=SEARCH_BODY)

        response = self.client.get(SEARCH_URL, {'q': '  Ляби   Хауз '})
        repeated = self.client.get(SEARCH_URL, {'q': 'ляби хауз'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), repeated.json())
        self.assertEqual(response.json()['data'], [
            {'label': 'Ляби-Хауз', 'address': 'улица Накшбанди, 5, Бухара', 'lat': 39.774, 'lng': 64.4198},
            {'label': 'Ташкент', 'address': 'Ташкент', 'lat': 41.3111, 'lng': 69.2797},
        ])
        self.assertEqual(len(self.requests), 1)
        params = self.requests[0].url.params
        self.assertEqual(self.requests[0].url.path, '/search')
        self.assertEqual(params['q'], 'ляби хауз')
        self.assertEqual(params['countrycodes'], 'uz')
        self.assertEqual(params['limit'], '5')
        self.assertIn('viewbox', params)

    def test_search_validates_query_length(self):
        for query in ('a', ' a ', 'x' * 121):
            with self.subTest(query=query):
                response = self.client.get(SEARCH_URL, {'q': query})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error']['code'], 'invalid_request')
        self.assertEqual(self.client.get(SEARCH_URL).status_code, 400)

    def test_upstream_failures_become_503_problems_and_are_not_cached(self):
        with self.assertLogs('store.geocoding.service', 'WARNING') as logs:
            self.assert_upstream_failures()
        self.assertTrue(all('39.77' not in line and 'Бухара' not in line for line in logs.output))
        self.assertEqual(len(self.requests), 4)

    def assert_upstream_failures(self):
        failures = [
            lambda request: httpx.Response(500, text='boom'),
            lambda request: httpx.Response(200, text='<html>'),
            lambda request: httpx.Response(200, json={'unexpected': True}),
        ]
        for reply in failures:
            self.reply = reply
            with self.subTest(reply=reply):
                response = self.client.get(SEARCH_URL, {'q': 'Бухара'})
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()['error']['code'], 'geocoder_unavailable')

        def timeout(request):
            raise httpx.ReadTimeout('slow', request=request)

        self.reply = timeout
        response = self.client.get(REVERSE_URL, {'lat': '39.77', 'lng': '64.42'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('39.77', response.content.decode())

    def test_clients_are_throttled_per_ip(self):
        for _ in range(GEOCODE_IP.limit):
            self.assertEqual(self.client.get(REVERSE_URL, {'lat': '39.77', 'lng': '64.42'}).status_code, 200)

        limited = self.client.get(REVERSE_URL, {'lat': '39.77', 'lng': '64.42'})

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()['error']['code'], 'rate_limited')
        self.assertIn('Retry-After', limited)
        self.assertEqual(len(self.requests), 1)

    def test_invalid_auth_header_does_not_block_public_endpoint(self):
        response = self.client.get(
            REVERSE_URL, {'lat': '39.77', 'lng': '64.42'}, HTTP_AUTHORIZATION='Token invalid',
        )

        self.assertEqual(response.status_code, 200)
