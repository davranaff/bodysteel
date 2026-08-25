from django.test import TestCase, override_settings

from users.auth.contact_verification import ContactVerificationService
from users.auth.errors import AuthProblem
from users.auth.models import AuthChallenge
from users.auth.ports import SmsDeliveryResult
from users.auth.test_registration import FakeSmsGateway, STRONG_PASSWORD
from users.models import User


CONTACT_SETTINGS = {
    'PHONE_VERIFICATION_HASH_KEY': 'c' * 48,
    'AUTH_RATE_LIMIT_HASH_KEY': 'r' * 48,
    'AUTH_CHALLENGE_HASH_KEY': 'a' * 48,
    'PASSWORD_RESET_TTL_SECONDS': '300',
    'PASSWORD_RESET_RESEND_SECONDS': '60',
    'PASSWORD_RESET_MAX_ATTEMPTS': '5',
}


@override_settings(**CONTACT_SETTINGS)
class ContactVerificationServiceTests(TestCase):
    def setUp(self):
        self.user = User(email='contact@example.test', phone='+998901234591')
        self.user.set_password(STRONG_PASSWORD)
        self.user.save()
        self.gateway = FakeSmsGateway(SmsDeliveryResult.SENT)
        self.service = ContactVerificationService(
            self.gateway,
            email_sender=lambda email, code: self.gateway.messages.append((email, code))
            or SmsDeliveryResult.SENT,
            code_generator=lambda length: '482901',
        )

    def test_email_contact_changes_only_after_valid_code(self):
        receipt = self.service.start(
            self.user, AuthChallenge.Channel.EMAIL, 'new-contact@example.test', '192.0.2.50',
        )
        self.assertEqual(self.user.email, 'contact@example.test')
        payload = self.service.complete(self.user, receipt.challenge_id, '482901')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new-contact@example.test')
        self.assertEqual(payload['email'], 'new-contact@example.test')
        with self.assertRaises(AuthProblem) as raised:
            self.service.complete(self.user, receipt.challenge_id, '482901')
        self.assertEqual(raised.exception.code, 'verification_failed')

    def test_phone_contact_wrong_codes_are_persisted(self):
        receipt = self.service.start(
            self.user, AuthChallenge.Channel.SMS, '+998901234592', '192.0.2.51',
        )
        with self.assertRaises(AuthProblem):
            self.service.complete(self.user, receipt.challenge_id, '000000')
        self.assertEqual(
            AuthChallenge.objects.get(pk=receipt.challenge_id).attempts_remaining,
            4,
        )
