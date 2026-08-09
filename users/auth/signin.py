from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework.authtoken.models import Token

from users.auth.errors import AuthProblem
from users.auth.presenter import user_payload
from users.auth.rate_limits import SIGNIN_IP, SIGNIN_PHONE, consume, reset
from users.models import User


DUMMY_PASSWORD_HASH = make_password('authentication-timing-placeholder')


class SignInService:
    def __init__(self, clock=timezone.now):
        self.clock = clock

    def sign_in(self, phone, password, remote_address):
        now = self.clock()
        consume(SIGNIN_PHONE, phone, now)
        consume(SIGNIN_IP, remote_address, now)
        user = User.objects.filter(phone=phone, is_active=True).first()
        valid = check_password(password, user.password if user else DUMMY_PASSWORD_HASH)
        if user is None or not valid:
            raise AuthProblem(401, 'invalid_credentials', 'Invalid phone or password')
        token, _ = Token.objects.get_or_create(user=user)
        reset(SIGNIN_PHONE, phone)
        return user_payload(user, token)
