import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.db import IntegrityError, transaction
from django.utils import timezone

from users.auth.errors import AuthProblem, configuration_problem
from users.auth.models import AuthRateLimit
from users.auth.security import rate_limit_digest


@dataclass(frozen=True)
class RateLimitPolicy:
    scope: str
    limit: int
    window_seconds: int


REGISTRATION_PHONE = RateLimitPolicy('registration_phone', 3, 600)
REGISTRATION_EMAIL = RateLimitPolicy('registration_email', 3, 600)
REGISTRATION_IP = RateLimitPolicy('registration_ip', 10, 600)
SIGNIN_PHONE = RateLimitPolicy('signin_phone', 5, 900)
SIGNIN_IP = RateLimitPolicy('signin_ip', 30, 900)
PASSWORD_RESET_IDENTIFIER = RateLimitPolicy('password_reset_identifier', 5, 900)
PASSWORD_RESET_IP = RateLimitPolicy('password_reset_ip', 20, 900)
CUSTOMER_TELEGRAM_USER = RateLimitPolicy('customer_telegram_user', 60, 60)
CUSTOMER_TELEGRAM_UPDATE = RateLimitPolicy('customer_telegram_update', 1, 86_400)
CUSTOMER_TELEGRAM_LINK = RateLimitPolicy('customer_telegram_link', 10, 300)


def consume(policy, subject, now=None):
    current_time = now or timezone.now()
    window_start = _window_start(current_time, policy.window_seconds)
    expires_at = window_start + timedelta(seconds=policy.window_seconds)
    digest = rate_limit_digest(policy.scope, subject)
    try:
        with transaction.atomic():
            record, _ = AuthRateLimit.objects.select_for_update().get_or_create(
                scope=policy.scope,
                subject_digest=digest,
                window_started_at=window_start,
                defaults={'count': 0, 'expires_at': expires_at},
            )
            if record.count >= policy.limit:
                raise _rate_limited(expires_at, current_time)
            record.count += 1
            record.expires_at = expires_at
            record.save(update_fields=['count', 'expires_at', 'updated_at'])
    except IntegrityError:
        raise configuration_problem() from None


def reset(policy, subject):
    digest = rate_limit_digest(policy.scope, subject)
    AuthRateLimit.objects.filter(scope=policy.scope, subject_digest=digest).delete()


def _window_start(value, window_seconds):
    timestamp = math.floor(value.timestamp() / window_seconds) * window_seconds
    return datetime.fromtimestamp(timestamp, tz=datetime_timezone.utc)


def _rate_limited(expires_at, current_time):
    retry_after = max(1, math.ceil((expires_at - current_time).total_seconds()))
    return AuthProblem(429, 'rate_limited', 'Too many attempts', retry_after)
