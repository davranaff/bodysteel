from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Q
from django.utils import timezone
from rest_framework.authtoken.models import Token

from users.auth.errors import AuthProblem
from users.auth.audit import record
from users.auth.presenter import user_payload
from users.auth.rate_limits import SIGNIN_IDENTIFIER, SIGNIN_IP, consume, reset
from users.models import User


DUMMY_PASSWORD_HASH = make_password('authentication-timing-placeholder')


class SignInService:
    def __init__(self, clock=timezone.now):
        self.clock = clock

    def sign_in(self, identifier, password, remote_address):
        now = self.clock()
        consume(SIGNIN_IDENTIFIER, identifier, now)
        consume(SIGNIN_IP, remote_address, now)
        user = User.objects.filter(
            Q(phone=identifier) | Q(email__iexact=identifier),
            is_active=True,
            deleted_at__isnull=True,
        ).first()
        valid = check_password(password, user.password if user else DUMMY_PASSWORD_HASH)
        if user is None or not valid:
            record('signin', 'failure')
            raise AuthProblem(401, 'invalid_credentials', 'Invalid identifier or password')
        token, _ = Token.objects.get_or_create(user=user)
        reset(SIGNIN_IDENTIFIER, identifier)
        record('signin', 'success', user_id=user.pk)
        return user_payload(user, token)
