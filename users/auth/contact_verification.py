import math
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from users.auth.configuration import password_reset_configuration
from users.auth.audit import record
from users.auth.errors import AuthProblem
from users.auth.local_delivery import send_email_otp
from users.auth.models import AuthChallenge
from users.auth.ports import SmsDeliveryResult
from users.auth.presenter import user_payload
from users.auth.rate_limits import CONTACT_CHANGE_TARGET, CONTACT_CHANGE_USER, consume, reset
from users.auth.security import auth_challenge_digest, auth_challenge_matches
from users.models import User
from users.utils.random_code import random_code


@dataclass(frozen=True)
class ContactVerificationReceipt:
    challenge_id: uuid.UUID
    expires_in: int
    resend_after: int


class ContactVerificationService:
    def __init__(self, sms_gateway, email_sender=send_email_otp, clock=timezone.now,
                 code_generator=random_code):
        self.sms_gateway = sms_gateway
        self.email_sender = email_sender
        self.clock = clock
        self.code_generator = code_generator

    def start(self, user, channel, identifier, remote_address):
        now = self.clock()
        if channel == AuthChallenge.Channel.EMAIL:
            identifier = identifier.lower()
        if self._already_used(user, channel, identifier):
            raise AuthProblem(409, 'contact_exists', 'Contact is already in use')
        consume(CONTACT_CHANGE_USER, str(user.pk), now)
        consume(CONTACT_CHANGE_TARGET, identifier, now)
        configuration = password_reset_configuration()
        kind = self._kind(channel)
        previous = AuthChallenge.objects.filter(
            user=user, kind=kind, identifier=identifier,
            status__in=(AuthChallenge.Status.PENDING, AuthChallenge.Status.SENT, AuthChallenge.Status.UNKNOWN),
        ).order_by('-created_at').first()
        if previous and now < previous.resend_after:
            seconds = max(1, math.ceil((previous.resend_after - now).total_seconds()))
            raise AuthProblem(429, 'resend_too_soon', 'Verification code was sent recently', seconds)
        code = self.code_generator(6)
        if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
            raise AuthProblem(503, 'service_unavailable', 'Authentication service unavailable')
        delivery_id = uuid.uuid4()
        challenge = AuthChallenge.objects.create(
            delivery_id=delivery_id,
            user=user,
            kind=kind,
            channel=channel,
            identifier=identifier,
            code_digest='',
            attempts_remaining=configuration.maximum_attempts,
            expires_at=now + timedelta(seconds=configuration.ttl_seconds),
            resend_after=now + timedelta(seconds=configuration.resend_seconds),
        )
        challenge.code_digest = auth_challenge_digest(challenge.id, delivery_id, code)
        challenge.save(update_fields=['code_digest', 'updated_at'])
        delivery = self._deliver(channel, identifier, code)
        updates = {'status': self._status(delivery), 'updated_at': now}
        if delivery is SmsDeliveryResult.SENT:
            updates['sent_at'] = now
        AuthChallenge.objects.filter(id=challenge.id, delivery_id=delivery_id).update(**updates)
        if delivery is SmsDeliveryResult.FAILED:
            raise AuthProblem(503, 'service_unavailable', 'Authentication service unavailable')
        record('contact_change_start', 'accepted', user_id=user.pk, channel=channel)
        return ContactVerificationReceipt(
            challenge.id,
            max(1, math.ceil((challenge.expires_at - now).total_seconds())),
            max(1, math.ceil((challenge.resend_after - now).total_seconds())),
        )

    def complete(self, user, challenge_id, code):
        now = self.clock()
        problem = None
        updated_user = None
        with transaction.atomic():
            challenge = AuthChallenge.objects.select_for_update().filter(
                id=challenge_id,
                user=user,
                kind__in=(AuthChallenge.Kind.EMAIL_VERIFICATION, AuthChallenge.Kind.PHONE_CHANGE),
            ).first()
            problem = self._challenge_problem(challenge, code, now)
            if problem is None:
                field = 'email' if challenge.channel == AuthChallenge.Channel.EMAIL else 'phone'
                lookup = {f'{field}__iexact': challenge.identifier} if field == 'email' else {field: challenge.identifier}
                if User.objects.filter(**lookup).exclude(pk=user.pk).exists():
                    problem = AuthProblem(409, 'contact_exists', 'Contact is already in use')
                else:
                    updated_user = type(user).objects.select_for_update().get(pk=user.pk)
                    setattr(updated_user, field, challenge.identifier)
                    setattr(updated_user, f'{field}_verified_at', now)
                    updated_user.save(update_fields=[field, f'{field}_verified_at'])
                    challenge.status = AuthChallenge.Status.CONSUMED
                    challenge.consumed_at = now
                    challenge.save(update_fields=['status', 'consumed_at', 'updated_at'])
        if problem:
            raise problem
        reset(CONTACT_CHANGE_TARGET, challenge.identifier)
        token, _ = Token.objects.get_or_create(user=updated_user)
        record('contact_change_complete', 'success', user_id=updated_user.pk, channel=challenge.channel)
        return user_payload(updated_user, token)

    @staticmethod
    def _already_used(user, channel, identifier):
        return (
            channel == AuthChallenge.Channel.EMAIL and user.email.lower() == identifier
        ) or (
            channel == AuthChallenge.Channel.SMS and user.phone == identifier
        )

    @staticmethod
    def _kind(channel):
        return AuthChallenge.Kind.EMAIL_VERIFICATION if channel == AuthChallenge.Channel.EMAIL else AuthChallenge.Kind.PHONE_CHANGE

    def _deliver(self, channel, identifier, code):
        if channel == AuthChallenge.Channel.EMAIL:
            return self.email_sender(identifier, code)
        return self.sms_gateway.send_otp(identifier, code)

    @staticmethod
    def _status(delivery):
        return {
            SmsDeliveryResult.SENT: AuthChallenge.Status.SENT,
            SmsDeliveryResult.UNKNOWN: AuthChallenge.Status.UNKNOWN,
            SmsDeliveryResult.FAILED: AuthChallenge.Status.FAILED,
        }[delivery]

    @staticmethod
    def _challenge_problem(challenge, code, now):
        if challenge is None:
            return AuthProblem(400, 'verification_failed', 'Verification failed')
        if challenge.expires_at <= now:
            return AuthProblem(410, 'verification_expired', 'Verification code expired')
        allowed = {AuthChallenge.Status.PENDING, AuthChallenge.Status.SENT, AuthChallenge.Status.UNKNOWN}
        if challenge.status not in allowed or challenge.attempts_remaining < 1:
            return AuthProblem(400, 'verification_failed', 'Verification failed')
        if auth_challenge_matches(challenge, code):
            return None
        challenge.attempts_remaining -= 1
        if challenge.attempts_remaining == 0:
            challenge.status = AuthChallenge.Status.LOCKED
        challenge.save(update_fields=['attempts_remaining', 'status', 'updated_at'])
        return AuthProblem(400, 'verification_failed', 'Verification failed')
