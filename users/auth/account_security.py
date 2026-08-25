import uuid

from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from users.auth.errors import AuthProblem
from users.auth.audit import record
from users.auth.presenter import user_payload


def rotate_token(user):
    Token.objects.filter(user=user).delete()
    return Token.objects.create(user=user)


def change_password(user, current_password, new_password):
    if not check_password(current_password, user.password):
        raise AuthProblem(401, 'invalid_credentials', 'Current password is incorrect')
    try:
        validate_password(new_password, user=user)
    except ValidationError:
        raise AuthProblem(400, 'invalid_password', 'Password does not meet requirements') from None
    user.set_password(new_password)
    user.save(update_fields=['password'])
    record('password_change', 'success', user_id=user.pk)
    return user_payload(user, rotate_token(user))


def delete_account(user, password, confirmation):
    if confirmation != 'DELETE' or not check_password(password, user.password):
        raise AuthProblem(400, 'delete_confirmation_failed', 'Account confirmation failed')
    with transaction.atomic():
        locked = type(user).objects.select_for_update().get(pk=user.pk)
        if not locked.is_active or locked.deleted_at is not None:
            raise AuthProblem(400, 'account_unavailable', 'Account is unavailable')
        from customer_telegram.links import unlink_user
        unlink_user(locked)
        suffix = uuid.uuid4().hex
        locked.username = f'deleted_{locked.pk}_{suffix[:16]}'[:100]
        locked.email = f'deleted.{locked.pk}.{suffix}@invalid.bodysteel.local'
        locked.phone = _deleted_phone(locked.pk, suffix)
        locked.first_name = ''
        locked.last_name = ''
        locked.is_active = False
        locked.is_staff = False
        locked.is_superuser = False
        locked.deleted_at = timezone.now()
        locked.phone_verified_at = None
        locked.email_verified_at = None
        locked.set_unusable_password()
        locked.save(update_fields=[
            'username', 'email', 'phone', 'first_name', 'last_name', 'is_active',
            'is_staff', 'is_superuser', 'deleted_at', 'phone_verified_at',
            'email_verified_at', 'password',
        ])
        Token.objects.filter(user=locked).delete()
        record('account_delete', 'success', user_id=locked.pk)


def revoke_all_sessions(user):
    Token.objects.filter(user=user).delete()


def session_payload(request):
    token = request.auth
    if not isinstance(token, Token):
        token = Token.objects.filter(user=request.user).first()
    if token is None:
        return []
    return [{
        'id': token.pk,
        'created_at': token.created.isoformat(),
        'current': True,
    }]


def _deleted_phone(user_id, suffix):
    value = int(suffix[:12], 16) % 1_000_000_000
    return f'+998{(value + user_id) % 1_000_000_000:09d}'
