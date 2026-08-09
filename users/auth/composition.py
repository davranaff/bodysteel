from functools import lru_cache

from users.auth.configuration import eskiz_configuration
from users.auth.eskiz import EskizSmsGateway
from users.auth.registration import RegistrationService
from users.auth.signin import SignInService


@lru_cache(maxsize=1)
def sms_gateway():
    return EskizSmsGateway(eskiz_configuration())


def registration_start_service():
    return RegistrationService(sms_gateway())


def registration_completion_service():
    return RegistrationService(None)


def sign_in_service():
    return SignInService()
