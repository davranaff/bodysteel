from datetime import datetime, timedelta, timezone as datetime_timezone

from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token

from users.auth.errors import AuthProblem
from users.auth.models import AuthChallenge
from users.auth.password_reset import PasswordResetService
from users.auth.test_registration import FakeSmsGateway, STRONG_PASSWORD
from users.models import User


RESET_SETTINGS = {
    'PHONE_VERIFICATION_HASH_KEY': 'c' * 48,
    'AUTH_RATE_LIMIT_HASH_KEY': 'r' * 48,
    'AUTH_CHALLENGE_HASH_KEY': 'a' * 48,
    'PASSWORD_RESET_TTL_SECONDS': '300',
    'PASSWORD_RESET_RESEND_SECONDS': '60',
    'PASSWORD_RESET_MAX_ATTEMPTS': '5',
}


class MutableClock:
    def __init__(self):
        self.value = datetime(2026, 8, 8, 6, 0, tzinfo=datetime_timezone.utc)

    def __call__(self):
        return self.value


@override_settings(**RESET_SETTINGS)
class PasswordResetServiceTests(TestCase):
    def setUp(self):
        self.clock = MutableClock()
        self.gateway = FakeSmsGateway()
        self.user = User(email='reset@example.test', phone='+998901234590')
        self.user.set_password(STRONG_PASSWORD)
        self.user.save()
        self.old_token = Token.objects.create(user=self.user)
        self.service = PasswordResetService(
            self.gateway,
            clock=self.clock,
            code_generator=lambda length: '482901',
        )

    def test_reset_is_single_use_and_rotates_token(self):
        receipt = self.service.start('+998901234590', '192.0.2.40')
        challenge = AuthChallenge.objects.get(pk=receipt.challenge_id)
        self.assertNotIn('482901', challenge.code_digest)
        payload = self.service.complete(receipt.challenge_id, '482901', 'New-BodySteel-2026!')

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-BodySteel-2026!'))
        self.assertEqual(payload['token'], Token.objects.get(user=self.user).key)
        self.assertNotEqual(payload['token'], self.old_token.key)
        with self.assertRaises(AuthProblem) as raised:
            self.service.complete(receipt.challenge_id, '482901', 'Another-BodySteel-2026!')
        self.assertEqual(raised.exception.code, 'verification_failed')

    def test_wrong_code_locks_challenge_and_expired_code_is_rejected(self):
        receipt = self.service.start('+998901234590', '192.0.2.41')
        for _ in range(5):
            with self.assertRaises(AuthProblem):
                self.service.complete(receipt.challenge_id, '000000', STRONG_PASSWORD)
        self.assertEqual(
            AuthChallenge.objects.get(pk=receipt.challenge_id).status,
            AuthChallenge.Status.LOCKED,
        )

        self.clock.value += timedelta(minutes=10)
        with self.assertRaises(AuthProblem) as raised:
            self.service.complete(receipt.challenge_id, '482901', STRONG_PASSWORD)
        self.assertEqual(raised.exception.code, 'verification_expired')

    def test_email_identifier_uses_email_delivery(self):
        sent = []
        service = PasswordResetService(
            self.gateway,
            email_sender=lambda email, code: sent.append((email, code)) or self.gateway.result,
            clock=self.clock,
            code_generator=lambda length: '173645',
        )
        receipt = service.start('RESET@EXAMPLE.TEST', '192.0.2.42')
        self.assertEqual(sent, [('reset@example.test', '173645')])
        service.complete(receipt.challenge_id, '173645', 'New-BodySteel-2026!')
