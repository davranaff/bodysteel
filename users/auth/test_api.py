import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from users.auth.ports import SmsDeliveryResult
from users.auth.registration import RegistrationService
from users.auth.test_registration import FakeSmsGateway, SECURITY_SETTINGS, STRONG_PASSWORD
from users.models import User


PROXY_TOKEN = 'storefront-proxy-token-with-at-least-32-characters'
API_SETTINGS = {
    **SECURITY_SETTINGS,
    'BODYSTEEL_STOREFRONT_PROXY_TOKEN': PROXY_TOKEN,
    'AUTH_TRUSTED_PROXY_NETWORKS': (),
}


@override_settings(**API_SETTINGS)
class AuthApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.gateway = FakeSmsGateway(SmsDeliveryResult.SENT)
        self.registration = RegistrationService(self.gateway)

    def test_two_step_registration_contract(self):
        with patch(
            'users.auth.views.registration_start_service',
            return_value=self.registration,
        ), patch(
            'users.auth.views.registration_completion_service',
            return_value=self.registration,
        ):
            started = self._post('/api/v1/users/phone_verification/', {
                'email': 'api@example.test',
                'phone': '+998901234570',
            })
            self.assertEqual(started.status_code, 201)
            self.assertEqual(started.headers['Content-Language'], 'ru')
            receipt = started.json()['data']
            self.assertEqual(set(receipt), {'challenge_id', 'expires_in', 'resend_after'})
            self.assertNotIn(self.gateway.messages[0][1], started.content.decode())
            self.assertFalse(User.objects.exists())

            completed = self._post('/api/v1/users/signup/', {
                'challenge_id': receipt['challenge_id'],
                'code': self.gateway.messages[0][1],
                'password': STRONG_PASSWORD,
                'password_confirm': STRONG_PASSWORD,
            })

        self.assertEqual(completed.status_code, 201)
        self.assertEqual(completed.json()['data']['phone'], '+998901234570')
        self.assertTrue(User.objects.filter(phone='+998901234570').exists())

    def test_proxy_token_language_and_exact_body_are_required(self):
        payload = {'email': 'api@example.test', 'phone': '+998901234570'}
        missing_token = self.client.post(
            '/api/v1/users/phone_verification/',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Accept-Language': 'ru'},
        )
        self.assertEqual(missing_token.status_code, 403)

        missing_language = self.client.post(
            '/api/v1/users/phone_verification/',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'X-Storefront-Proxy-Token': PROXY_TOKEN},
        )
        self.assertEqual(missing_language.status_code, 406)

        invalid_body = self._post('/api/v1/users/phone_verification/', {
            **payload,
            'role': 'admin',
        })
        self.assertEqual(invalid_body.status_code, 400)
        self.assertEqual(invalid_body.json()['error']['code'], 'invalid_request')

    def test_signin_uses_one_generic_failure_and_rate_limits_phone(self):
        user = User(email='signin@example.test', phone='+998901234571')
        user.set_password(STRONG_PASSWORD)
        user.save()

        for phone in ['+998901234571', '+998901234572']:
            response = self._post('/api/v1/users/signin/', {
                'phone': phone,
                'password': 'wrong-password',
            })
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()['error']['code'], 'invalid_credentials')

        for _ in range(4):
            self._post('/api/v1/users/signin/', {
                'phone': '+998901234571',
                'password': 'wrong-password',
            })
        limited = self._post('/api/v1/users/signin/', {
            'phone': '+998901234571',
            'password': 'wrong-password',
        })
        self.assertEqual(limited.status_code, 429)
        self.assertIn('Retry-After', limited.headers)

    def _post(self, path, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type='application/json',
            headers={
                'X-Storefront-Proxy-Token': PROXY_TOKEN,
                'Accept-Language': 'ru',
            },
        )
