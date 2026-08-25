from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings, skipUnlessDBFeature

from users.auth.errors import AuthProblem
from users.auth.models import AuthChallenge, AuthRateLimit
from users.auth.password_reset import PasswordResetService
from users.auth.rate_limits import RateLimitPolicy, consume
from users.auth.registration import RegistrationService
from users.auth.test_registration import (
    FakeSmsGateway,
    SECURITY_SETTINGS,
    STRONG_PASSWORD,
)
from users.models import User


@override_settings(**SECURITY_SETTINGS)
class RateLimitConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_requests_cannot_exceed_limit(self):
        policy = RateLimitPolicy('concurrent_test', 3, 600)
        barrier = Barrier(5)

        def attempt():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                try:
                    consume(policy, 'same-subject')
                    return 'accepted'
                except AuthProblem as problem:
                    return problem.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = [future.result(timeout=10) for future in [
                executor.submit(attempt) for _ in range(5)
            ]]

        self.assertEqual(results.count('accepted'), 3)
        self.assertEqual(results.count('rate_limited'), 2)
        self.assertEqual(AuthRateLimit.objects.get().count, 3)

    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_registration_start_sends_only_one_code(self):
        gateway = FakeSmsGateway()
        barrier = Barrier(2)

        def start():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                try:
                    RegistrationService(
                        gateway,
                        code_generator=lambda length: '482901',
                    ).start('race@example.test', '+998901234580', '192.0.2.20')
                    return 'accepted'
                except AuthProblem as problem:
                    return problem.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [future.result(timeout=10) for future in [
                executor.submit(start), executor.submit(start),
            ]]

        self.assertCountEqual(results, ['accepted', 'resend_too_soon'])
        self.assertEqual(len(gateway.messages), 1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_verification_consumes_challenge_once(self):
        gateway = FakeSmsGateway()
        service = RegistrationService(gateway, code_generator=lambda length: '482901')
        receipt = service.start('verify@example.test', '+998901234581', '192.0.2.21')
        barrier = Barrier(2)

        def complete():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                try:
                    RegistrationService(None).complete(
                        receipt.challenge_id, '482901', STRONG_PASSWORD,
                    )
                    return 'accepted'
                except AuthProblem as problem:
                    return problem.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [future.result(timeout=10) for future in [
                executor.submit(complete), executor.submit(complete),
            ]]

        self.assertCountEqual(results, ['accepted', 'verification_failed'])
        self.assertEqual(User.objects.filter(phone='+998901234581').count(), 1)

    @skipUnlessDBFeature('has_select_for_update')
    @override_settings(
        AUTH_CHALLENGE_HASH_KEY='a' * 48,
        PASSWORD_RESET_TTL_SECONDS='300',
        PASSWORD_RESET_RESEND_SECONDS='60',
        PASSWORD_RESET_MAX_ATTEMPTS='5',
    )
    def test_concurrent_password_reset_start_sends_only_one_code(self):
        User.objects.create_user(
            username='reset-race', email='reset-race@example.test',
            phone='+998901234582', password=STRONG_PASSWORD,
        )
        gateway = FakeSmsGateway()
        barrier = Barrier(2)

        def start():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                try:
                    PasswordResetService(
                        gateway, code_generator=lambda length: '482901',
                    ).start('+998901234582', '192.0.2.22')
                    return 'accepted'
                except AuthProblem as problem:
                    return problem.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [future.result(timeout=10) for future in [
                executor.submit(start), executor.submit(start),
            ]]

        self.assertCountEqual(results, ['accepted', 'resend_too_soon'])
        self.assertEqual(len(gateway.messages), 1)
        self.assertEqual(
            AuthChallenge.objects.filter(
                identifier='+998901234582',
                status=AuthChallenge.Status.SENT,
            ).count(),
            1,
        )
