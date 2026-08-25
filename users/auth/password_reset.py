import math
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.authtoken.models import Token

from users.auth.configuration import password_reset_configuration
from users.auth.audit import record
from users.auth.errors import AuthProblem
from users.auth.local_delivery import send_email_otp
from users.auth.models import AuthChallenge
from users.auth.ports import SmsDeliveryResult
from users.auth.presenter import user_payload
from users.auth.rate_limits import (
    PASSWORD_RESET_IDENTIFIER,
    PASSWORD_RESET_IP,
    consume,
    reset,
)
from users.auth.security import auth_challenge_digest, auth_challenge_matches
from users.models import User
from users.utils.random_code import random_code


@dataclass(frozen=True)
class PasswordResetReceipt:
    challenge_id: uuid.UUID
    expires_in: int
    resend_after: int


class PasswordResetService:
    def __init__(self, sms_gateway, email_sender=send_email_otp, clock=timezone.now,
                 code_generator=random_code):
        self.sms_gateway = sms_gateway
        self.email_sender = email_sender
        self.clock = clock
        self.code_generator = code_generator

    def start(self, identifier, remote_address):
        now = self.clock()
        identifier = identifier.lower() if '@' in identifier else identifier
        configuration = password_reset_configuration()
        code = self.code_generator(6)
        if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
            raise AuthProblem(503, 'service_unavailable', 'Authentication service unavailable')
        challenge, user, channel = self._prepare(
            identifier, remote_address, configuration, now, code=code,
        )

        delivery = SmsDeliveryResult.SENT
        if user is not None:
            delivery = self._deliver(channel, identifier, code)
        status = {
            SmsDeliveryResult.SENT: AuthChallenge.Status.SENT,
            SmsDeliveryResult.UNKNOWN: AuthChallenge.Status.UNKNOWN,
            SmsDeliveryResult.FAILED: AuthChallenge.Status.FAILED,
        }[delivery]
        updates = {'status': status, 'updated_at': now}
        if delivery is SmsDeliveryResult.SENT:
            updates['sent_at'] = now
        AuthChallenge.objects.filter(
            id=challenge.id, delivery_id=challenge.delivery_id,
        ).update(**updates)
        # Keep the forgot-password response neutral even if delivery fails for a real account.
        # Operators can inspect the delivery provider metrics without exposing account existence.
        record('password_reset_start', 'accepted', user_id=user.pk if user else None, channel=channel)
        return PasswordResetReceipt(
            challenge.id,
            max(1, math.ceil((challenge.expires_at - now).total_seconds())),
            max(1, math.ceil((challenge.resend_after - now).total_seconds())),
        )

    def start_telegram(self, identifier, remote_address):
        now = self.clock()
        identifier = identifier.lower() if '@' in identifier else identifier
        configuration = password_reset_configuration()
        challenge, user, _ = self._prepare(
            identifier, remote_address, configuration, now, telegram=True,
        )
        record(
            'password_reset_start', 'accepted',
            user_id=user.pk if user else None, channel=AuthChallenge.Channel.TELEGRAM,
        )
        return PasswordResetReceipt(
            challenge.id,
            max(1, math.ceil((challenge.expires_at - now).total_seconds())),
            max(1, math.ceil((challenge.resend_after - now).total_seconds())),
        )

    def _prepare(self, identifier, remote_address, configuration, now, code=None, telegram=False):
        problem = None
        challenge = user = channel = None
        with transaction.atomic():
            # The identifier rate-limit row is also the per-flow serialization lock.
            consume(PASSWORD_RESET_IDENTIFIER, identifier, now)
            consume(PASSWORD_RESET_IP, remote_address, now)
            previous = AuthChallenge.objects.select_for_update().filter(
                kind=AuthChallenge.Kind.PASSWORD_RESET,
                identifier=identifier,
                status__in=(
                    AuthChallenge.Status.AWAITING,
                    AuthChallenge.Status.PENDING,
                    AuthChallenge.Status.SENT,
                    AuthChallenge.Status.UNKNOWN,
                ),
            ).order_by('-created_at').first()
            if previous and now < previous.resend_after:
                seconds = max(1, math.ceil((previous.resend_after - now).total_seconds()))
                problem = AuthProblem(
                    429, 'resend_too_soon', 'Verification code was sent recently', seconds,
                )
            else:
                if previous:
                    previous.status = AuthChallenge.Status.FAILED
                    previous.save(update_fields=('status', 'updated_at'))
                user, default_channel = self._find_target(identifier)
                channel = AuthChallenge.Channel.TELEGRAM if telegram else default_channel
                delivery_id = uuid.uuid4()
                challenge = AuthChallenge.objects.create(
                    delivery_id=delivery_id, user=user,
                    kind=AuthChallenge.Kind.PASSWORD_RESET, channel=channel,
                    identifier=identifier, code_digest='',
                    status=(AuthChallenge.Status.AWAITING if telegram else AuthChallenge.Status.PENDING),
                    attempts_remaining=configuration.maximum_attempts,
                    expires_at=now + timedelta(seconds=configuration.ttl_seconds),
                    resend_after=now + timedelta(seconds=configuration.resend_seconds),
                )
                if code is not None:
                    challenge.code_digest = auth_challenge_digest(challenge.id, delivery_id, code)
                    challenge.save(update_fields=('code_digest', 'updated_at'))
        if problem:
            raise problem
        return challenge, user, channel

    def complete(self, challenge_id, code, password):
        now = self.clock()
        problem = None
        user = None
        token = None
        with transaction.atomic():
            challenge = AuthChallenge.objects.select_for_update().filter(
                id=challenge_id,
                kind=AuthChallenge.Kind.PASSWORD_RESET,
            ).first()
            problem = self._challenge_problem(challenge, code, now)
            if problem is None:
                user = challenge.user
                if user is None or not user.is_active or user.deleted_at is not None:
                    problem = AuthProblem(400, 'verification_failed', 'Verification failed')
                else:
                    try:
                        validate_password(password, user=user)
                    except ValidationError:
                        problem = AuthProblem(
                            400, 'invalid_password', 'Password does not meet requirements',
                        )
                    if problem is None:
                        user.set_password(password)
                        user.save(update_fields=['password'])
                        Token.objects.filter(user=user).delete()
                        token = Token.objects.create(user=user)
                        challenge.status = AuthChallenge.Status.CONSUMED
                        challenge.consumed_at = now
                        challenge.save(update_fields=['status', 'consumed_at', 'updated_at'])
                        if challenge.channel == AuthChallenge.Channel.TELEGRAM:
                            from customer_telegram.lifecycle import consume_password_reset_link
                            consume_password_reset_link(challenge, now)
        if problem:
            raise problem
        reset(PASSWORD_RESET_IDENTIFIER, challenge.identifier)
        record('password_reset_complete', 'success', user_id=user.pk, channel=challenge.channel)
        return user_payload(user, token)

    @staticmethod
    def _find_target(identifier):
        if identifier.startswith('+'):
            return User.objects.filter(
                phone=identifier, is_active=True, deleted_at__isnull=True,
            ).first(), AuthChallenge.Channel.SMS
        return User.objects.filter(
            email__iexact=identifier, is_active=True, deleted_at__isnull=True,
        ).first(), AuthChallenge.Channel.EMAIL

    def _deliver(self, channel, identifier, code):
        if channel == AuthChallenge.Channel.SMS:
            return self.sms_gateway.send_otp(identifier, code)
        return self.email_sender(identifier, code)

    @staticmethod
    def _challenge_problem(challenge, code, now):
        if challenge is None:
            return AuthProblem(400, 'verification_failed', 'Verification failed')
        if challenge.expires_at <= now:
            return AuthProblem(410, 'verification_expired', 'Verification code expired')
        allowed = {
            AuthChallenge.Status.PENDING,
            AuthChallenge.Status.SENT,
            AuthChallenge.Status.UNKNOWN,
        }
        if challenge.status not in allowed or challenge.attempts_remaining < 1:
            return AuthProblem(400, 'verification_failed', 'Verification failed')
        if auth_challenge_matches(challenge, code):
            return None
        challenge.attempts_remaining -= 1
        if challenge.attempts_remaining == 0:
            challenge.status = AuthChallenge.Status.LOCKED
        challenge.save(update_fields=['attempts_remaining', 'status', 'updated_at'])
        return AuthProblem(400, 'verification_failed', 'Verification failed')
