from collections import OrderedDict
from threading import Lock
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from users.auth.ports import SmsDeliveryResult


class LocalCodeStore:
    """Process-local delivery sink used only by the development environment."""

    def __init__(self, maximum=128):
        self.maximum = maximum
        self._values = OrderedDict()
        self._lock = Lock()

    def put(self, channel, recipient, code, ttl_seconds=900):
        key = (channel, recipient)
        with self._lock:
            self._values[key] = (code, timezone.now() + timedelta(seconds=ttl_seconds))
            self._values.move_to_end(key)
            while len(self._values) > self.maximum:
                self._values.popitem(last=False)

    def get(self, channel, recipient):
        key = (channel, recipient)
        with self._lock:
            value = self._values.get(key)
            if value is None:
                return None
            code, expires_at = value
            if expires_at <= timezone.now():
                self._values.pop(key, None)
                return None
            return code


local_code_store = LocalCodeStore()


class LocalSmsGateway:
    def send_otp(self, phone, code):
        local_code_store.put('sms', phone, code)
        return SmsDeliveryResult.SENT


def send_email_otp(email, code):
    backend = getattr(settings, 'AUTH_EMAIL_BACKEND', 'smtp')
    if settings.DEBUG or backend == 'local':
        local_code_store.put('email', email, code)
        return SmsDeliveryResult.SENT
    try:
        sent = send_mail(
            'BodySteel verification code',
            f'Your BodySteel verification code is {code}.',
            getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            [email],
            fail_silently=False,
        )
    except Exception:
        return SmsDeliveryResult.FAILED
    return SmsDeliveryResult.SENT if sent == 1 else SmsDeliveryResult.UNKNOWN


def local_code(channel, recipient):
    if not settings.DEBUG:
        return None
    return local_code_store.get(channel, recipient)
