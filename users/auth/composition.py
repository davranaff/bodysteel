from functools import lru_cache

from django.conf import settings

from users.auth.configuration import eskiz_configuration
from users.auth.eskiz import EskizSmsGateway
from users.auth.local_delivery import LocalSmsGateway
from users.auth.password_reset import PasswordResetService
from users.auth.contact_verification import ContactVerificationService
from users.auth.registration import RegistrationService
from users.auth.signin import SignInService


@lru_cache(maxsize=1)
def sms_gateway():
    if settings.DEBUG and getattr(settings, 'SMS_BACKEND', '') in {'local', 'disabled'}:
        return LocalSmsGateway()
    return EskizSmsGateway(eskiz_configuration())


def registration_start_service():
    return RegistrationService(sms_gateway())


def registration_completion_service():
    return RegistrationService(None)


def registration_telegram_start_service():
    return RegistrationService(None)


def sign_in_service():
    return SignInService()


def password_reset_service():
    return PasswordResetService(sms_gateway())


def password_reset_telegram_service():
    return PasswordResetService(None)


def password_reset_completion_service():
    return PasswordResetService(None)


def contact_verification_service():
    return ContactVerificationService(sms_gateway())
