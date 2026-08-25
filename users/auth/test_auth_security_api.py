import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from rest_framework.authtoken.models import Token

from users.auth.contact_verification import ContactVerificationService
from users.auth.errors import AuthProblem
from users.auth.models import AuthChallenge
from users.auth.password_reset import PasswordResetService
from users.auth.ports import SmsDeliveryResult
from users.auth.registration import RegistrationService
from users.auth.test_registration import FakeSmsGateway, SECURITY_SETTINGS, STRONG_PASSWORD
from users.models import User


PROXY_TOKEN = 'storefront-proxy-token-with-at-least-32-characters'
API_SETTINGS = {
    **SECURITY_SETTINGS,
    'AUTH_CHALLENGE_HASH_KEY': 'a' * 48,
    'PASSWORD_RESET_TTL_SECONDS': '300',
    'PASSWORD_RESET_RESEND_SECONDS': '60',
    'PASSWORD_RESET_MAX_ATTEMPTS': '5',
    'BODYSTEEL_STOREFRONT_PROXY_TOKEN': PROXY_TOKEN,
    'AUTH_TRUSTED_PROXY_NETWORKS': (),
}


@override_settings(**API_SETTINGS)
class AuthSecurityApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_extended_registration_and_email_signin(self):
        gateway = FakeSmsGateway()
        registration = RegistrationService(gateway, code_generator=lambda length: '482901')
        with patch('users.auth.views.registration_start_service', return_value=registration), patch(
            'users.auth.views.registration_completion_service', return_value=registration,
        ):
            started = self._public_post('/api/v1/users/phone_verification/', {
                'email': 'extended@example.test',
                'phone': '+998901234593',
                'username': 'extended-shopper',
                'first_name': 'Ali',
                'last_name': 'Valiyev',
            })
            self.assertEqual(started.status_code, 201)
            challenge_id = started.json()['data']['challenge_id']
            self.assertNotIn('482901', started.content.decode())

            completed = self._public_post('/api/v1/users/signup/', {
                'challenge_id': challenge_id,
                'code': gateway.messages[0][1],
                'password': STRONG_PASSWORD,
                'password_confirm': STRONG_PASSWORD,
            })

        self.assertEqual(completed.status_code, 201)
        user = User.objects.get(username='extended-shopper')
        self.assertEqual(user.first_name, 'Ali')
        self.assertEqual(user.last_name, 'Valiyev')
        self.assertIsNotNone(user.phone_verified_at)

        signed_in = self._public_post('/api/v1/users/signin/', {
            'identifier': 'EXTENDED@EXAMPLE.TEST',
            'password': STRONG_PASSWORD,
        })
        self.assertEqual(signed_in.status_code, 200)
        self.assertEqual(signed_in.json()['data']['username'], 'extended-shopper')

    def test_password_reset_is_neutral_and_rotates_the_old_session(self):
        user = self._user('reset-api@example.test', '+998901234594')
        old_token = Token.objects.create(user=user)
        gateway = FakeSmsGateway()
        reset = PasswordResetService(gateway, code_generator=lambda length: '173645')
        with patch('users.auth.views.password_reset_service', return_value=reset):
            unknown = self._public_post('/api/v1/users/password/forgot/', {
                'identifier': '+998901234595',
            })
            known = self._public_post('/api/v1/users/password/forgot/', {
                'identifier': user.phone,
            })
            self.assertEqual(unknown.status_code, 202)
            self.assertEqual(known.status_code, 202)
            self.assertNotIn('173645', known.content.decode())

            challenge = AuthChallenge.objects.get(
                identifier=user.phone,
                kind=AuthChallenge.Kind.PASSWORD_RESET,
            )
            completed = self._public_post('/api/v1/users/password/reset/', {
                'challenge_id': str(challenge.id),
                'code': '173645',
                'password': 'New-BodySteel-2026!',
                'password_confirm': 'New-BodySteel-2026!',
            })

        self.assertEqual(completed.status_code, 200)
        self.assertNotEqual(completed.json()['data']['token'], old_token.key)
        self.assertFalse(Token.objects.filter(key=old_token.key).exists())
        with self.assertRaises(AuthProblem) as raised:
            reset.complete(challenge.id, '173645', 'Another-BodySteel-2026!')
        self.assertEqual(raised.exception.code, 'verification_failed')

    def test_private_account_security_soft_deletes_and_blocks_reentry(self):
        user = self._user('delete-api@example.test', '+998901234596')
        token = Token.objects.create(user=user)
        unauthenticated = self.client.get('/api/v1/users/me/')
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.json()['error']['code'], 'unauthorized')

        profile = self._private_get('/api/v1/users/me/', token)
        self.assertEqual(profile.status_code, 200)
        self.assertNotIn('password', profile.content.decode())

        wrong_password = self._private_put('/api/v1/users/password/change/', token, {
            'current_password': 'wrong-pass',
            'new_password': 'New-BodySteel-2026!',
            'new_password_confirm': 'New-BodySteel-2026!',
        })
        self.assertEqual(wrong_password.status_code, 401)

        sessions = self._private_get('/api/v1/users/sessions/', token)
        self.assertEqual(sessions.status_code, 200)
        self.assertEqual(sessions.json()['data'][0]['current'], True)

        invalid_delete = self._private_post('/api/v1/users/delete/', token, {
            'password': STRONG_PASSWORD,
            'confirmation': 'delete',
        })
        self.assertEqual(invalid_delete.status_code, 400)

        deleted = self._private_post('/api/v1/users/delete/', token, {
            'password': STRONG_PASSWORD,
            'confirmation': 'DELETE',
        })
        self.assertEqual(deleted.status_code, 204)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.deleted_at)
        self.assertFalse(Token.objects.filter(user=user).exists())

        old_session = self._private_get('/api/v1/users/me/', token)
        self.assertEqual(old_session.status_code, 401)
        blocked = self._public_post('/api/v1/users/signin/', {
            'identifier': 'delete-api@example.test',
            'password': STRONG_PASSWORD,
        })
        self.assertEqual(blocked.status_code, 401)

    def test_contact_verification_changes_email_only_after_otp(self):
        user = self._user('contact-api@example.test', '+998901234597')
        token = Token.objects.create(user=user)
        gateway = FakeSmsGateway(SmsDeliveryResult.SENT)
        contact = ContactVerificationService(
            gateway,
            email_sender=lambda email, code: gateway.messages.append((email, code))
            or SmsDeliveryResult.SENT,
            code_generator=lambda length: '482901',
        )
        with patch('users.profile.views.contact_verification_service', return_value=contact):
            started = self._private_post('/api/v1/users/email/change/start/', token, {
                'email': 'new-contact-api@example.test',
            })
            self.assertEqual(started.status_code, 201)
            challenge_id = started.json()['data']['challenge_id']
            wrong = self._private_post('/api/v1/users/contact/verify/', token, {
                'challenge_id': challenge_id,
                'code': '000000',
            })
            self.assertEqual(wrong.status_code, 400)
            user.refresh_from_db()
            self.assertEqual(user.email, 'contact-api@example.test')

            verified = self._private_post('/api/v1/users/contact/verify/', token, {
                'challenge_id': challenge_id,
                'code': '482901',
            })

        self.assertEqual(verified.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, 'new-contact-api@example.test')
        self.assertIsNotNone(user.email_verified_at)

    def _public_post(self, path, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type='application/json',
            headers={
                'X-Storefront-Proxy-Token': PROXY_TOKEN,
                'Accept-Language': 'ru',
                'REMOTE_ADDR': '192.0.2.99',
            },
        )

    def _private_get(self, path, token):
        return self.client.get(path, headers={'Authorization': f'Token {token.key}'})

    def _private_put(self, path, token, payload):
        return self.client.put(
            path,
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': f'Token {token.key}'},
        )

    def _private_post(self, path, token, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': f'Token {token.key}'},
        )

    @staticmethod
    def _user(email, phone):
        user = User(email=email, phone=phone, username=email.split('@')[0])
        user.set_password(STRONG_PASSWORD)
        user.save()
        return user
