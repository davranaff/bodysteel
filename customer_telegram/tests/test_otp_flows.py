import re
import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase, override_settings
from django.utils import timezone

from customer_telegram.links import (
    open_link,
    start_account_link,
    start_password_reset,
    start_registration,
    unlink_user,
)
from customer_telegram.models import CustomerTelegramChat, CustomerTelegramLink
from customer_telegram.otp import _record_delivery, process_contact
from customer_telegram.otp import deliver_linked_reset
from customer_telegram.security import link_digest
from customer_telegram.bot_api import DeliveryStatus
from customer_telegram.tests.base import FakeTelegramApi, TELEGRAM_SETTINGS
from users.auth.composition import password_reset_completion_service, registration_completion_service
from users.auth.errors import AuthProblem
from users.auth.models import AuthChallenge, PhoneVerificationChallenge
from users.models import User


PASSWORD = 'Correct-Horse-Battery-2026!'


@override_settings(**TELEGRAM_SETTINGS)
class TelegramOtpFlowTests(TestCase):
    def test_registration_delivers_digest_only_and_links_after_completion(self):
        receipt = start_registration(self.identity(), '192.0.2.10', 'ru')
        token = self.token(receipt.telegram_url)
        self.assertLessEqual(len(token), 64)
        self.assertNotIn('+998', receipt.telegram_url)
        started = open_link(token, 1001, 1001)
        self.assertTrue(started.requires_contact)

        api = FakeTelegramApi()
        outcome = process_contact(
            started.link.pk, 1001, 1001,
            {'user_id': 1001, 'phone_number': '998901234567'}, api,
        )
        self.assertEqual(outcome.status, 'delivered')
        challenge = PhoneVerificationChallenge.objects.get(pk=receipt.challenge_id)
        self.assertEqual(challenge.status, PhoneVerificationChallenge.Status.SENT)
        code = self.code(api)
        self.assertNotIn(code, challenge.code_digest)
        self.assertFalse(CustomerTelegramChat.objects.get(chat_id=1001).user_id)

        payload = registration_completion_service().complete(challenge.pk, code, PASSWORD)
        user = User.objects.get(pk=payload['id'])
        self.assertEqual(CustomerTelegramChat.objects.get(chat_id=1001).user, user)
        self.assertEqual(CustomerTelegramLink.objects.get(pk=started.link.pk).state, 'consumed')
        with self.assertRaises(AuthProblem):
            registration_completion_service().complete(challenge.pk, code, PASSWORD)

    def test_contact_mismatch_locks_after_bounded_attempts(self):
        receipt = start_registration(self.identity(), '192.0.2.11', 'uz')
        link = open_link(self.token(receipt.telegram_url), 1002, 1002).link
        for expected in (2, 1, 0):
            outcome = process_contact(
                link.pk, 1002, 1002,
                {'user_id': 1002, 'phone_number': '998909999999'}, FakeTelegramApi(),
            )
            self.assertEqual(outcome.status, 'mismatch')
            link.refresh_from_db()
            self.assertEqual(link.contact_attempts_remaining, expected)
        self.assertEqual(link.state, CustomerTelegramLink.LOCKED)

    def test_forwarded_or_manual_contact_is_rejected(self):
        receipt = start_registration(self.identity(), '192.0.2.17', 'ru')
        link = open_link(self.token(receipt.telegram_url), 1017, 1017).link
        outcome = process_contact(
            link.pk, 1017, 1017,
            {'user_id': 9999, 'phone_number': '+998901234567'},
            FakeTelegramApi(),
        )
        self.assertEqual(outcome.status, 'mismatch')
        link.refresh_from_db()
        self.assertEqual(link.contact_attempts_remaining, 2)

    def test_missing_contact_owner_and_duplicate_contact_are_rejected(self):
        receipt = start_registration(self.identity(), '192.0.2.21', 'ru')
        link = open_link(self.token(receipt.telegram_url), 1021, 1021).link
        missing_owner = process_contact(
            link.pk, 1021, 1021,
            {'phone_number': '+998901234567'}, FakeTelegramApi(),
        )
        self.assertEqual(missing_owner.status, 'mismatch')
        api = FakeTelegramApi()
        delivered = process_contact(
            link.pk, 1021, 1021,
            {'user_id': 1021, 'phone_number': '(998) 90 123-45-67'}, api,
        )
        self.assertEqual(delivered.status, 'delivered')
        duplicate = process_contact(
            link.pk, 1021, 1021,
            {'user_id': 1021, 'phone_number': '+998901234567'}, FakeTelegramApi(),
        )
        self.assertEqual(duplicate.status, 'invalid')
        self.assertEqual(len(api.messages), 1)

    def test_expired_link_cannot_consume_contact_attempt(self):
        receipt = start_registration(self.identity(), '192.0.2.18', 'ru')
        link = open_link(self.token(receipt.telegram_url), 1018, 1018).link
        link.expires_at = timezone.now() - timedelta(seconds=1)
        link.save(update_fields=('expires_at', 'updated_at'))
        outcome = process_contact(
            link.pk, 1018, 1018,
            {'user_id': 9999, 'phone_number': '+998901234567'},
            FakeTelegramApi(),
        )
        self.assertEqual(outcome.status, 'invalid')
        link.refresh_from_db()
        self.assertEqual(link.state, CustomerTelegramLink.EXPIRED)
        self.assertEqual(link.contact_attempts_remaining, 3)

    def test_claimed_link_cannot_be_taken_over_by_another_telegram_user(self):
        receipt = start_registration(self.identity(), '192.0.2.14', 'ru')
        token = self.token(receipt.telegram_url)
        claimed = open_link(token, 1014, 1014)
        self.assertIsNotNone(claimed.link)
        self.assertIsNone(open_link(token, 2014, 2014).link)
        self.assertEqual(CustomerTelegramLink.objects.get(pk=claimed.link.pk).chat_id, claimed.link.chat_id)

    def test_resend_replaces_old_deep_link(self):
        first = start_registration(self.identity(), '192.0.2.16', 'ru')
        challenge = PhoneVerificationChallenge.objects.get(pk=first.challenge_id)
        challenge.resend_after = timezone.now() - timedelta(seconds=1)
        challenge.save(update_fields=('resend_after', 'updated_at'))
        second = start_registration(self.identity(), '192.0.2.16', 'ru')

        self.assertIsNone(open_link(self.token(first.telegram_url), 1016, 1016).link)
        self.assertIsNotNone(open_link(self.token(second.telegram_url), 1016, 1016).link)

    def test_replaced_password_reset_link_cannot_revive_failed_challenge(self):
        receipt = start_password_reset('missing@example.test', '192.0.2.15', 'ru')
        challenge = AuthChallenge.objects.get(pk=receipt.challenge_id)
        challenge.status = AuthChallenge.Status.FAILED
        challenge.save(update_fields=('status', 'updated_at'))

        self.assertIsNone(open_link(self.token(receipt.telegram_url), 1015, 1015).link)
        link = CustomerTelegramLink.objects.get(auth_challenge=challenge)
        self.assertEqual(link.state, CustomerTelegramLink.EXPIRED)

    def test_late_delivery_response_cannot_mark_replacement_link_delivered(self):
        receipt = start_registration(self.identity(), '192.0.2.22', 'ru')
        link = open_link(self.token(receipt.telegram_url), 1022, 1022).link
        challenge = PhoneVerificationChallenge.objects.get(pk=receipt.challenge_id)
        old_delivery_id = challenge.delivery_id
        challenge.status = PhoneVerificationChallenge.Status.PENDING
        challenge.save(update_fields=('status', 'updated_at'))
        link.state = CustomerTelegramLink.DELIVERING
        link.save(update_fields=('state', 'updated_at'))

        challenge.delivery_id = uuid.uuid4()
        challenge.status = PhoneVerificationChallenge.Status.AWAITING
        challenge.save(update_fields=('delivery_id', 'status', 'updated_at'))
        link.state = CustomerTelegramLink.AWAITING_START
        link.chat = None
        link.save(update_fields=('state', 'chat', 'updated_at'))

        self.assertFalse(_record_delivery(
            link.pk, old_delivery_id, DeliveryStatus.SENT, timezone.now(),
        ))
        link.refresh_from_db()
        challenge.refresh_from_db()
        self.assertEqual(link.state, CustomerTelegramLink.AWAITING_START)
        self.assertEqual(challenge.status, PhoneVerificationChallenge.Status.AWAITING)

    def test_password_reset_is_neutral_and_can_link_existing_account(self):
        user = User.objects.create_user(
            username='reset-user', email='reset@example.test', phone='+998901234568', password=PASSWORD,
        )
        receipt = start_password_reset(user.email, '192.0.2.12', 'ru')
        link = open_link(self.token(receipt.telegram_url), 1003, 1003).link
        api = FakeTelegramApi()
        outcome = process_contact(
            link.pk, 1003, 1003,
            {'user_id': 1003, 'phone_number': '+998901234568'}, api,
        )
        self.assertEqual(outcome.status, 'delivered')
        code = self.code(api)
        password_reset_completion_service().complete(
            receipt.challenge_id, code, 'Another-Safe-Password-2026!',
        )
        self.assertEqual(CustomerTelegramChat.objects.get(chat_id=1003).user, user)
        link.refresh_from_db()
        self.assertEqual(link.state, CustomerTelegramLink.CONSUMED)

        missing = start_password_reset('missing@example.test', '192.0.2.13', 'ru')
        missing_link = open_link(self.token(missing.telegram_url), 1004, 1004).link
        missing_api = FakeTelegramApi()
        outcome = process_contact(
            missing_link.pk, 1004, 1004,
            {'user_id': 1004, 'phone_number': '+998901234569'}, missing_api,
        )
        self.assertEqual(outcome.status, 'mismatch')
        self.assertEqual(missing_api.messages, [])
        self.assertIsNone(AuthChallenge.objects.get(pk=missing.challenge_id).user_id)

    def test_authenticated_account_link_and_unlink(self):
        user = User.objects.create_user(
            username='existing', email='existing@example.test', phone='+998901234570', password=PASSWORD,
        )
        receipt = start_account_link(user, 'uz')
        link = open_link(self.token(receipt.telegram_url), 1005, 1005).link
        outcome = process_contact(
            link.pk, 1005, 1005,
            {'user_id': 1005, 'phone_number': '998901234570'}, FakeTelegramApi(),
        )
        self.assertEqual(outcome.status, 'linked')
        chat = CustomerTelegramChat.objects.get(chat_id=1005)
        self.assertEqual(chat.user, user)
        chat.marketing_opt_in = True
        chat.save(update_fields=('marketing_opt_in',))
        self.assertTrue(unlink_user(user))
        chat.refresh_from_db()
        self.assertIsNone(chat.user_id)
        self.assertFalse(chat.marketing_opt_in)

    def test_atomic_relink_clears_consent_on_both_conflicting_chats(self):
        target = User.objects.create_user(
            username='target', email='target@example.test',
            phone='+998901234573', password=PASSWORD,
        )
        previous = CustomerTelegramChat.objects.create(
            user=target, telegram_user_id=1073, chat_id=1073,
            language='ru', marketing_opt_in=True,
        )
        former_owner = User.objects.create_user(
            username='former', email='former@example.test',
            phone='+998901234574', password=PASSWORD,
        )
        current = CustomerTelegramChat.objects.create(
            user=former_owner, telegram_user_id=2073, chat_id=2073,
            language='ru', marketing_opt_in=True,
        )
        link = open_link(self.token(start_account_link(target, 'ru').telegram_url), 2073, 2073).link
        self.assertEqual(process_contact(
            link.pk, 2073, 2073,
            {'user_id': 2073, 'phone_number': target.phone}, FakeTelegramApi(),
        ).status, 'linked')
        previous.refresh_from_db()
        current.refresh_from_db()
        self.assertIsNone(previous.user_id)
        self.assertFalse(previous.marketing_opt_in)
        self.assertEqual(current.user, target)
        self.assertFalse(current.marketing_opt_in)

    def test_linked_account_reset_skips_contact_but_remains_single_use(self):
        user = User.objects.create_user(
            username='linked-reset', email='linked-reset@example.test',
            phone='+998901234575', password=PASSWORD,
        )
        CustomerTelegramChat.objects.create(
            user=user, telegram_user_id=1075, chat_id=1075, language='uz',
        )
        receipt = start_password_reset(user.email, '192.0.2.75', 'uz')
        started = open_link(self.token(receipt.telegram_url), 1075, 1075)
        self.assertFalse(started.requires_contact)
        api = FakeTelegramApi()
        self.assertEqual(
            deliver_linked_reset(started.link.pk, 1075, 1075, api).status,
            'delivered',
        )
        self.assertEqual(
            deliver_linked_reset(started.link.pk, 1075, 1075, FakeTelegramApi()).status,
            'invalid',
        )

    def test_inactive_user_cannot_finish_account_link(self):
        user = User.objects.create_user(
            username='inactive-link', email='inactive-link@example.test',
            phone='+998901234576', password=PASSWORD,
        )
        receipt = start_account_link(user, 'ru')
        user.is_active = False
        user.save(update_fields=('is_active',))
        self.assertIsNone(open_link(self.token(receipt.telegram_url), 1076, 1076).link)

    def test_deep_link_prefix_must_match_persisted_purpose(self):
        receipt = start_registration(self.identity(), '192.0.2.19', 'ru')
        token = self.token(receipt.telegram_url)
        wrong_token = 'p{}'.format(token[1:])
        CustomerTelegramLink.objects.filter(
            registration_challenge_id=receipt.challenge_id,
        ).update(token_digest=link_digest(wrong_token))
        self.assertIsNone(open_link(wrong_token, 1019, 1019).link)

    def test_deep_link_has_bounded_per_link_rate_limit(self):
        receipt = start_registration(self.identity(), '192.0.2.20', 'ru')
        token = self.token(receipt.telegram_url)
        for _ in range(10):
            self.assertIsNotNone(open_link(token, 1020, 1020).link)
        self.assertIsNone(open_link(token, 1020, 1020).link)

    @staticmethod
    def identity():
        return {
            'email': 'shopper@example.test', 'phone': '+998901234567',
            'username': 'shopper', 'first_name': 'Shopper', 'last_name': 'Test',
        }

    @staticmethod
    def token(url):
        return parse_qs(urlsplit(url).query)['start'][0]

    @staticmethod
    def code(api):
        match = re.search(r'<code>(\d{6})</code>', api.messages[0][1])
        return match.group(1)
