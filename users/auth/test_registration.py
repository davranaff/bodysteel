from datetime import datetime, timedelta, timezone as datetime_timezone

from django.test import TestCase, override_settings

from users.auth.errors import AuthProblem
from users.auth.models import PhoneVerificationChallenge
from users.auth.ports import SmsDeliveryResult
from users.auth.registration import RegistrationService
from users.models import User


SECURITY_SETTINGS = {
    'PHONE_VERIFICATION_HASH_KEY': 'c' * 48,
    'AUTH_RATE_LIMIT_HASH_KEY': 'r' * 48,
    'PHONE_VERIFICATION_TTL_SECONDS': '300',
    'PHONE_VERIFICATION_RESEND_SECONDS': '60',
    'PHONE_VERIFICATION_MAX_ATTEMPTS': '5',
}
STRONG_PASSWORD = 'BodySteel-secure-2026!'


class FakeSmsGateway:
    def __init__(self, result=SmsDeliveryResult.SENT):
        self.result = result
        self.messages = []

    def send_otp(self, phone, code):
        self.messages.append((phone, code))
        return self.result


class MutableClock:
    def __init__(self):
        self.value = datetime(2026, 8, 8, 6, 0, tzinfo=datetime_timezone.utc)

    def __call__(self):
        return self.value


@override_settings(**SECURITY_SETTINGS)
class RegistrationServiceTests(TestCase):
    def setUp(self):
        self.clock = MutableClock()
        self.gateway = FakeSmsGateway()
        self.service = RegistrationService(
            self.gateway,
            clock=self.clock,
            code_generator=lambda length: '482901',
        )

    def test_user_is_created_only_after_valid_single_use_code(self):
        receipt = self._start()

        self.assertFalse(User.objects.exists())
        challenge = PhoneVerificationChallenge.objects.get(pk=receipt.challenge_id)
        self.assertNotEqual(challenge.code_digest, '482901')
        self.assertNotIn('482901', challenge.code_digest)
        self.assertEqual(len(challenge.code_digest), 64)

        payload = self.service.complete(receipt.challenge_id, '482901', STRONG_PASSWORD)

        user = User.objects.get(phone='+998901234567')
        self.assertEqual(payload['id'], user.pk)
        self.assertTrue(user.check_password(STRONG_PASSWORD))
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, PhoneVerificationChallenge.Status.CONSUMED)
        with self.assertRaises(AuthProblem) as raised:
            self.service.complete(receipt.challenge_id, '482901', STRONG_PASSWORD)
        self.assertEqual(raised.exception.code, 'verification_failed')

    def test_wrong_codes_are_persisted_and_lock_the_challenge(self):
        receipt = self._start()

        for remaining in reversed(range(5)):
            with self.assertRaises(AuthProblem):
                self.service.complete(receipt.challenge_id, '000000', STRONG_PASSWORD)
            challenge = PhoneVerificationChallenge.objects.get(pk=receipt.challenge_id)
            self.assertEqual(challenge.attempts_remaining, remaining)

        self.assertEqual(challenge.status, PhoneVerificationChallenge.Status.LOCKED)
        with self.assertRaises(AuthProblem):
            self.service.complete(receipt.challenge_id, '482901', STRONG_PASSWORD)
        self.assertFalse(User.objects.exists())

    def test_expired_code_is_rejected(self):
        receipt = self._start()
        self.clock.value += timedelta(seconds=301)

        with self.assertRaises(AuthProblem) as raised:
            self.service.complete(receipt.challenge_id, '482901', STRONG_PASSWORD)

        self.assertEqual(raised.exception.status, 410)
        self.assertEqual(raised.exception.code, 'verification_expired')

    def test_resend_overwrites_code_after_cooldown(self):
        receipt = self._start()
        with self.assertRaises(AuthProblem) as raised:
            self._start()
        self.assertEqual(raised.exception.code, 'resend_too_soon')

        self.clock.value += timedelta(seconds=61)
        service = RegistrationService(
            self.gateway,
            clock=self.clock,
            code_generator=lambda length: '173645',
        )
        resent = service.start('shopper@example.test', '+998901234567', '192.0.2.10')

        self.assertEqual(resent.challenge_id, receipt.challenge_id)
        with self.assertRaises(AuthProblem):
            service.complete(receipt.challenge_id, '482901', STRONG_PASSWORD)
        payload = service.complete(receipt.challenge_id, '173645', STRONG_PASSWORD)
        self.assertEqual(payload['phone'], '+998901234567')

    def test_delivery_failure_is_explicit_but_unknown_delivery_remains_verifiable(self):
        failed = RegistrationService(
            FakeSmsGateway(SmsDeliveryResult.FAILED),
            clock=self.clock,
            code_generator=lambda length: '482901',
        )
        with self.assertRaises(AuthProblem) as raised:
            failed.start('failed@example.test', '+998901234568', '192.0.2.11')
        self.assertEqual(raised.exception.code, 'sms_unavailable')
        self.assertEqual(
            PhoneVerificationChallenge.objects.get(phone='+998901234568').status,
            PhoneVerificationChallenge.Status.FAILED,
        )

        unknown = RegistrationService(
            FakeSmsGateway(SmsDeliveryResult.UNKNOWN),
            clock=self.clock,
            code_generator=lambda length: '752816',
        )
        receipt = unknown.start('unknown@example.test', '+998901234569', '192.0.2.12')
        payload = unknown.complete(receipt.challenge_id, '752816', STRONG_PASSWORD)
        self.assertEqual(payload['email'], 'unknown@example.test')

    def _start(self):
        return self.service.start(
            'shopper@example.test', '+998901234567', '192.0.2.10',
        )
