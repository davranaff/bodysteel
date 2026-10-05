import hashlib
import hmac
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token

from users.models import User
from users.savdoq.client import IssuedSession, SavdoqRefused, SavdoqUnavailable
from users.savdoq.configuration import require_configuration
from users.savdoq.models import SavdoqShopperSession
from users.savdoq.sessions import ShopperSessionService


PROXY_TOKEN = 'storefront-proxy-token-with-at-least-32-characters'
IDENTITY_KEY = 'i' * 48
SERVICE_TOKEN = 's' * 48
SAVDOQ_SETTINGS = {
    'BODYSTEEL_STOREFRONT_PROXY_TOKEN': PROXY_TOKEN,
    'SAVDOQ_API_ORIGIN': 'https://rag.example.test',
    'SAVDOQ_STOREFRONT_ORIGIN': 'https://shop.example.test',
    'SAVDOQ_WIDGET_PUBLIC_KEY': 'wpk_' + 'a' * 32,
    'SAVDOQ_SHOPPER_SERVICE_TOKEN': SERVICE_TOKEN,
    'SAVDOQ_SHOPPER_IDENTITY_KEY': IDENTITY_KEY,
}
SESSION_URL = '/api/v1/users/savdoq/session/'


class FakeSavdoqClient:
    def __init__(self, error=None, revoke_error=None):
        self.issued = []
        self.revoked = []
        self.error = error
        self.revoke_error = revoke_error

    def issue(self, subject_hash, language):
        if self.error:
            raise self.error
        self.issued.append((subject_hash, language))
        return IssuedSession(
            access_token=f'widget-session-{len(self.issued)}',
            expires_at=timezone.now() + timedelta(minutes=15),
            session_id=uuid.uuid4(),
        )

    def revoke(self, subject_hash):
        self.revoked.append(subject_hash)
        if self.revoke_error:
            raise self.revoke_error


@override_settings(**SAVDOQ_SETTINGS)
class ShopperChatSessionApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chat-shopper', email='chat@example.test', phone='+998901234599',
            password='unused-password-1',
        )
        self.token = Token.objects.create(user=self.user)
        self.client = Client()
        self.fake = FakeSavdoqClient()
        service = patch(
            'users.savdoq.views.shopper_session_service',
            side_effect=lambda: ShopperSessionService(require_configuration(), self.fake),
        )
        service.start()
        self.addCleanup(service.stop)

    def post(self, token=None, proxy=PROXY_TOKEN, language='ru', mode=None, data=None):
        headers = {'HTTP_ACCEPT_LANGUAGE': language}
        if token is not False:
            headers['HTTP_AUTHORIZATION'] = f'Token {token or self.token.key}'
        if proxy:
            headers['HTTP_X_STOREFRONT_PROXY_TOKEN'] = proxy
        if mode:
            headers['HTTP_X_SAVDOQ_SESSION'] = mode
        return self.client.post(
            SESSION_URL, data or {}, content_type='application/json', **headers,
        )

    def test_issues_a_session_for_the_signed_in_customer_without_leaking_secrets(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        data = response.json()['data']
        self.assertEqual(data['session']['accessToken'], 'widget-session-1')
        self.assertEqual(data['session']['tokenType'], 'Bearer')
        self.assertIs(data['session']['shopperAuthenticated'], True)
        self.assertTrue(data['session']['expiresAt'].endswith('Z'))
        uuid.UUID(data['session']['sessionId'])
        self.assertEqual(data['site'], {
            'apiOrigin': 'https://rag.example.test', 'publicKey': 'wpk_' + 'a' * 32,
        })
        body = response.content.decode()
        for secret in (SERVICE_TOKEN, IDENTITY_KEY, self.token.key):
            self.assertNotIn(secret, body)

    def test_subject_hash_matches_the_former_storefront_bridge(self):
        self.post(language='uz')
        expected = hmac.new(
            IDENTITY_KEY.encode(), f'bodysteel:v1:{self.user.pk}'.encode(), hashlib.sha256,
        ).hexdigest()
        self.assertEqual(self.fake.issued, [(expected, 'uz')])

    def test_reuses_the_session_until_a_new_conversation_is_requested(self):
        first = self.post().json()['data']['session']
        again = self.post().json()['data']['session']
        self.assertEqual(again['accessToken'], first['accessToken'])
        self.assertEqual(len(self.fake.issued), 1)
        fresh = self.post(mode='new').json()['data']['session']
        self.assertNotEqual(fresh['accessToken'], first['accessToken'])
        self.assertEqual(self.post().json()['data']['session'], fresh)
        self.assertEqual(SavdoqShopperSession.objects.filter(user=self.user).count(), 1)

    def test_a_rotated_sign_in_never_reuses_the_previous_session(self):
        first = self.post().json()['data']['session']
        self.token.delete()
        self.token = Token.objects.create(user=self.user)
        self.assertNotEqual(self.post().json()['data']['session']['accessToken'], first['accessToken'])

    def test_boundary_rejects_unauthenticated_untrusted_or_malformed_requests(self):
        self.assertEqual(self.post(token=False).status_code, 401)
        self.assertEqual(self.post(proxy=None).status_code, 403)
        self.assertEqual(self.post(proxy='x' * 40).status_code, 403)
        self.assertEqual(self.post(language='en').status_code, 406)
        self.assertEqual(self.post(mode='reuse').status_code, 400)
        self.assertEqual(self.post(data={'customerId': 1}).status_code, 400)
        self.assertEqual(self.fake.issued, [])

    def test_savdoq_refusals_are_actionable_and_outages_stay_private(self):
        cases = (
            (SavdoqRefused(429, retry_after=17), 429, 'chat_rate_limited'),
            (SavdoqRefused(403), 403, 'chat_refused'),
            (SavdoqUnavailable('status 500'), 503, 'chat_unavailable'),
        )
        for error, status, code in cases:
            self.fake.error = error
            response = self.post()
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()['error']['code'], code)
        self.fake.error = SavdoqRefused(429, retry_after=17)
        self.assertEqual(self.post().headers['Retry-After'], '17')

    @override_settings(SAVDOQ_SHOPPER_SERVICE_TOKEN='')
    def test_missing_configuration_is_a_private_outage(self):
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'chat_unavailable')


@override_settings(**SAVDOQ_SETTINGS)
class ShopperChatRevocationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='leaving-shopper', email='leave@example.test', phone='+998901234598',
            password='unused-password-1',
        )
        self.token = Token.objects.create(user=self.user)
        SavdoqShopperSession.objects.create(
            user=self.user, language='ru', credential_digest='0' * 64,
            access_token='stored-session', expires_at=timezone.now() + timedelta(minutes=10),
        )

    def sign_out(self, fake):
        with patch(
            'users.savdoq.sessions.shopper_session_service',
            side_effect=lambda: ShopperSessionService(require_configuration(), fake),
        ):
            return Client().post(
                '/api/v1/users/signout/', HTTP_AUTHORIZATION=f'Token {self.token.key}',
            )

    def test_sign_out_revokes_stored_and_remote_sessions(self):
        fake = FakeSavdoqClient()
        self.assertEqual(self.sign_out(fake).status_code, 204)
        self.assertFalse(SavdoqShopperSession.objects.filter(user=self.user).exists())
        self.assertEqual(len(fake.revoked), 1)

    def test_a_failed_revocation_is_reported_and_keeps_the_customer_signed_in(self):
        fake = FakeSavdoqClient(revoke_error=SavdoqUnavailable('down'))
        response = self.sign_out(fake)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'service_unavailable')
        self.assertTrue(Token.objects.filter(user=self.user).exists())

    @override_settings(
        SAVDOQ_API_ORIGIN='', SAVDOQ_WIDGET_PUBLIC_KEY='',
        SAVDOQ_SHOPPER_SERVICE_TOKEN='', SAVDOQ_SHOPPER_IDENTITY_KEY='',
    )
    def test_sign_out_without_chat_configuration_still_clears_stored_sessions(self):
        fake = FakeSavdoqClient()
        self.assertEqual(self.sign_out(fake).status_code, 204)
        self.assertFalse(SavdoqShopperSession.objects.filter(user=self.user).exists())
        self.assertEqual(fake.revoked, [])

    def test_password_change_and_revoke_all_revoke_chat_first(self):
        fake = FakeSavdoqClient(revoke_error=SavdoqUnavailable('down'))
        with patch(
            'users.savdoq.sessions.shopper_session_service',
            side_effect=lambda: ShopperSessionService(require_configuration(), fake),
        ):
            response = Client().post(
                '/api/v1/users/sessions/revoke-all/',
                HTTP_AUTHORIZATION=f'Token {self.token.key}',
            )
        self.assertEqual(response.status_code, 503)
        self.assertTrue(Token.objects.filter(user=self.user).exists())
