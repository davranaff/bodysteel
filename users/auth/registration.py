import math
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.authtoken.models import Token

from users.auth.configuration import verification_configuration
from users.auth.errors import AuthProblem
from users.auth.models import PhoneVerificationChallenge
from users.auth.ports import SmsDeliveryResult
from users.auth.presenter import user_payload
from users.auth.rate_limits import (
    REGISTRATION_EMAIL,
    REGISTRATION_IP,
    REGISTRATION_PHONE,
    consume,
)
from users.auth.security import otp_digest, otp_matches
from users.models import User
from users.utils.random_code import random_code
from users.utils.random_username import random_username


@dataclass(frozen=True)
class VerificationReceipt:
    challenge_id: uuid.UUID
    expires_in: int
    resend_after: int


class RegistrationService:
    def __init__(self, sms_gateway, clock=timezone.now, code_generator=random_code):
        self.sms_gateway = sms_gateway
        self.clock = clock
        self.code_generator = code_generator

    def start(self, email, phone, remote_address):
        now = self.clock()
        self._consume_start_limits(email, phone, remote_address, now)
        configuration = verification_configuration()
        code = self.code_generator(6)
        if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
            raise AuthProblem(503, 'service_unavailable', 'Authentication service unavailable')
        challenge, delivery_id = self._prepare_challenge(
            email, phone, code, configuration, now,
        )
        delivery = self.sms_gateway.send_otp(phone, code)
        if not self._record_delivery(challenge.id, delivery_id, delivery, now):
            raise AuthProblem(409, 'challenge_superseded', 'Request a new verification code')
        if delivery is SmsDeliveryResult.FAILED:
            raise AuthProblem(503, 'sms_unavailable', 'Verification message could not be sent')
        return VerificationReceipt(
            challenge.id,
            max(1, math.ceil((challenge.expires_at - now).total_seconds())),
            max(1, math.ceil((challenge.resend_after - now).total_seconds())),
        )

    def complete(self, challenge_id, code, password):
        now = self.clock()
        problem = None
        try:
            with transaction.atomic():
                challenge = PhoneVerificationChallenge.objects.select_for_update().filter(
                    id=challenge_id,
                ).first()
                problem = self._challenge_problem(challenge, code, now)
                if problem is None:
                    user = self._create_user(challenge, password)
                    token, _ = Token.objects.get_or_create(user=user)
                    challenge.status = PhoneVerificationChallenge.Status.CONSUMED
                    challenge.consumed_at = now
                    challenge.save(update_fields=['status', 'consumed_at', 'updated_at'])
        except IntegrityError:
            raise AuthProblem(409, 'account_exists', 'Account already exists') from None
        if problem:
            raise problem
        return user_payload(user, token)

    def _prepare_challenge(self, email, phone, code, configuration, now):
        delivery_id = uuid.uuid4()
        expires_at = now + timedelta(seconds=configuration.ttl_seconds)
        resend_after = now + timedelta(seconds=configuration.resend_seconds)
        with transaction.atomic():
            self._reject_existing_account(email, phone)
            challenge, created = PhoneVerificationChallenge.objects.select_for_update().get_or_create(
                phone=phone,
                defaults={
                    'email': email,
                    'delivery_id': delivery_id,
                    'code_digest': '',
                    'expires_at': expires_at,
                    'resend_after': resend_after,
                },
            )
            if not created and now < challenge.resend_after:
                seconds = max(1, math.ceil((challenge.resend_after - now).total_seconds()))
                raise AuthProblem(429, 'resend_too_soon', 'Verification code was sent recently', seconds)
            challenge.email = email
            challenge.delivery_id = delivery_id
            challenge.code_digest = otp_digest(challenge.id, delivery_id, code)
            challenge.status = PhoneVerificationChallenge.Status.PENDING
            challenge.attempts_remaining = configuration.maximum_attempts
            challenge.expires_at = expires_at
            challenge.resend_after = resend_after
            challenge.sent_at = None
            challenge.consumed_at = None
            challenge.save()
        return challenge, delivery_id

    def _record_delivery(self, challenge_id, delivery_id, delivery, now):
        status = {
            SmsDeliveryResult.SENT: PhoneVerificationChallenge.Status.SENT,
            SmsDeliveryResult.UNKNOWN: PhoneVerificationChallenge.Status.UNKNOWN,
            SmsDeliveryResult.FAILED: PhoneVerificationChallenge.Status.FAILED,
        }[delivery]
        updates = {'status': status, 'updated_at': now}
        if delivery is SmsDeliveryResult.SENT:
            updates['sent_at'] = now
        return bool(PhoneVerificationChallenge.objects.filter(
            id=challenge_id,
            delivery_id=delivery_id,
            status=PhoneVerificationChallenge.Status.PENDING,
        ).update(**updates))

    def _challenge_problem(self, challenge, code, now):
        if challenge is None:
            return AuthProblem(400, 'verification_failed', 'Verification failed')
        if challenge.expires_at <= now:
            return AuthProblem(410, 'verification_expired', 'Verification code expired')
        allowed = {
            PhoneVerificationChallenge.Status.PENDING,
            PhoneVerificationChallenge.Status.SENT,
            PhoneVerificationChallenge.Status.UNKNOWN,
        }
        if challenge.status not in allowed or challenge.attempts_remaining < 1:
            return AuthProblem(400, 'verification_failed', 'Verification failed')
        if otp_matches(challenge, code):
            return None
        challenge.attempts_remaining -= 1
        if challenge.attempts_remaining == 0:
            challenge.status = PhoneVerificationChallenge.Status.LOCKED
        challenge.save(update_fields=['attempts_remaining', 'status', 'updated_at'])
        return AuthProblem(400, 'verification_failed', 'Verification failed')

    @staticmethod
    def _create_user(challenge, password):
        candidate = User(email=challenge.email, phone=challenge.phone, username=random_username())
        try:
            validate_password(password, user=candidate)
        except ValidationError:
            raise AuthProblem(400, 'invalid_password', 'Password does not meet requirements') from None
        candidate.set_password(password)
        candidate.save()
        return candidate

    @staticmethod
    def _reject_existing_account(email, phone):
        if User.objects.filter(Q(phone=phone) | Q(email__iexact=email)).exists():
            raise AuthProblem(409, 'account_exists', 'Account already exists')

    @staticmethod
    def _consume_start_limits(email, phone, remote_address, now):
        consume(REGISTRATION_PHONE, phone, now)
        consume(REGISTRATION_EMAIL, email, now)
        consume(REGISTRATION_IP, remote_address, now)
