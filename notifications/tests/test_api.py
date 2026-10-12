import json
import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token

from notifications.configuration import token_cipher
from notifications.models import PushDevice
from notifications.tests.fixtures import PUSH_SETTINGS, device_values, shopper


@override_settings(**PUSH_SETTINGS)
class DeviceApiTests(TestCase):
    def setUp(self):
        self.user = shopper()
        self.token = Token.objects.create(user=self.user)
        self.installation = uuid.uuid4()
        self.path = '/api/v1/users/push/devices/{}/'.format(self.installation)
        self.headers = {'HTTP_AUTHORIZATION': 'Token ' + self.token.key, 'HTTP_ACCEPT_LANGUAGE': 'ru',
            'HTTP_X_STOREFRONT_PROXY_TOKEN': PUSH_SETTINGS['BODYSTEEL_STOREFRONT_PROXY_TOKEN']}

    def put(self, body=None, **headers):
        return self.client.put(self.path, json.dumps(body or device_values()), content_type='application/json',
                               **{**self.headers, **headers})

    def test_token_is_encrypted_and_never_echoed(self):
        response = self.put(HTTP_ACCEPT_LANGUAGE='uz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Language'], 'uz')
        record = PushDevice.objects.get(installation_id=self.installation)
        self.assertEqual(token_cipher().decrypt(record.token_ciphertext.encode()).decode(), device_values()['token'])
        self.assertNotIn(device_values()['token'], record.token_ciphertext)
        self.assertNotIn('token', response.json()['data'])
        self.assertEqual(self.client.get(self.path, **self.headers).status_code, 200)

    def test_requires_customer_and_proxy_and_language(self):
        self.assertEqual(self.put(HTTP_AUTHORIZATION='').status_code, 401)
        self.assertEqual(self.put(HTTP_X_STOREFRONT_PROXY_TOKEN='').status_code, 403)
        self.assertEqual(self.put(HTTP_ACCEPT_LANGUAGE='en').status_code, 406)
        self.assertFalse(PushDevice.objects.exists())

    def test_unknown_identity_and_demographic_fields_are_rejected(self):
        for field in ('user_id', 'age', 'weight', 'gender'):
            self.assertEqual(self.put({**device_values(), field: 10}).status_code, 400)
        self.assertFalse(PushDevice.objects.exists())

    def test_repeated_registration_and_permission_withdrawal(self):
        self.put()
        original = PushDevice.objects.get().registration_scope
        self.put()
        self.assertEqual(PushDevice.objects.count(), 1)
        self.assertEqual(PushDevice.objects.get().registration_scope, original)
        self.put(device_values(permission='denied'))
        record = PushDevice.objects.get()
        self.assertFalse(record.is_active)
        self.assertEqual(record.token_ciphertext, '')

    def test_new_owner_cannot_inherit_opt_in_or_old_scope(self):
        self.put()
        previous = PushDevice.objects.get().registration_scope
        other = shopper(2)
        token = Token.objects.create(user=other)
        values = device_values()
        values.pop('marketing_opt_in')
        self.put(values, HTTP_AUTHORIZATION='Token ' + token.key)
        record = PushDevice.objects.get()
        self.assertEqual(record.user_id, other.pk)
        self.assertFalse(record.marketing_opt_in)
        self.assertNotEqual(record.registration_scope, previous)
        self.assertEqual(self.client.get(self.path, **self.headers).status_code, 404)

    def test_delete_is_owned_and_idempotent(self):
        self.put()
        other = shopper(2)
        token = Token.objects.create(user=other)
        self.client.delete(self.path, **{**self.headers, 'HTTP_AUTHORIZATION': 'Token ' + token.key})
        self.assertTrue(PushDevice.objects.get().is_active)
        for _ in range(2):
            self.assertEqual(self.client.delete(self.path, **self.headers).status_code, 204)
        self.assertFalse(PushDevice.objects.get().is_active)

    def test_missing_key_is_explicit_and_private(self):
        with override_settings(PUSH_TOKEN_ENCRYPTION_KEYS=()):
            response = self.put()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(device_values()['token'], response.content.decode())
        self.assertFalse(PushDevice.objects.exists())

    def test_signout_deactivates_the_device(self):
        self.put()
        with patch('users.profile.views.revoke_shopper_chat'):
            response = self.client.post('/api/v1/users/signout/', **self.headers)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(PushDevice.objects.get().is_active)
        self.assertEqual(PushDevice.objects.get().token_ciphertext, '')
        self.assertIsNone(PushDevice.objects.get().token_digest)

    def test_http_boundary_rejects_unbounded_ambiguous_and_unknown_input(self):
        cases = [
            ('{"platform":"ios","platform":"android"}', 400, 'application/json'),
            ('{"permission":NaN}', 400, 'application/json'),
            ('[1,2,3]', 400, 'application/json'),
            ('{"model":"' + 'x' * 17000 + '"}', 413, 'application/json'),
            ('{}', 415, 'text/plain'),
            ('{', 400, 'application/json'),
        ]
        for body, expected, content_type in cases:
            with self.subTest(expected=expected, content_type=content_type):
                response = self.client.put(self.path, body, content_type=content_type, **self.headers)
                self.assertEqual(response.status_code, expected)
        self.assertEqual(self.client.get(self.path + '?user_id=1', **self.headers).status_code, 400)
        self.assertEqual(self.client.delete(self.path, '{}', content_type='application/json', **self.headers).status_code, 400)
        self.assertFalse(PushDevice.objects.exists())
