import hashlib
import hmac
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from notifications.configuration import token_cipher
from notifications.models import PushDevice
from users.auth.errors import AuthProblem
from users.models import User


def credential_digest(user_id, key):
    return hmac.new(settings.SECRET_KEY.encode(), f'push:{user_id}:{key}'.encode(), hashlib.sha256).hexdigest()


def device_payload(device):
    return {'registration_scope': str(device.registration_scope), 'platform': device.platform,
            'permission': device.permission, 'marketing_opt_in': device.marketing_opt_in,
            'active': device.is_active, 'language': device.language}


def register_device(user, credential, installation_id, values, language):
    try:
        return _register_device(user, credential, installation_id, values, language)
    except IntegrityError:
        raise AuthProblem(409, 'registration_conflict', 'Device registration changed; retry') from None


def _register_device(user, credential, installation_id, values, language):
    granted = values['permission'] in ('authorized', 'provisional')
    token = values.get('token', '') if granted else ''
    encrypted = token_cipher().encrypt(token.encode()).decode() if token else ''
    digest = hashlib.sha256(token.encode()).hexdigest() if token else None
    with transaction.atomic():
        owner = User.objects.select_for_update().get(pk=user.pk)
        if not owner.is_active or owner.deleted_at or not Token.objects.filter(user=owner, key=credential.key).exists():
            raise AuthProblem(401, 'unauthenticated', 'Session unavailable')
        device = PushDevice.objects.select_for_update().filter(installation_id=installation_id).first()
        if granted and (not device or not device.is_active or device.user_id != owner.pk):
            if PushDevice.objects.filter(user=owner, is_active=True).count() >= settings.PUSH_MAX_DEVICES_PER_USER:
                raise AuthProblem(429, 'device_limit', 'Too many registered devices', retry_after=3600)
        if digest:
            PushDevice.objects.filter(token_digest=digest).exclude(installation_id=installation_id).update(
                is_active=False, token_digest=None, token_ciphertext='', registration_scope=uuid.uuid4())
        changed_owner = device is None or device.user_id != owner.pk
        if device is None:
            device = PushDevice(installation_id=installation_id, user=owner)
        if changed_owner or not device.is_active:
            device.registration_scope = uuid.uuid4()
        device.marketing_opt_in = values.get('marketing_opt_in', False if changed_owner else device.marketing_opt_in)
        device.user = owner
        for field in ('platform', 'model', 'os_version', 'app_version', 'app_build', 'permission'):
            setattr(device, field, values[field])
        device.language = language
        device.is_active = granted
        device.token_ciphertext = encrypted
        device.token_digest = digest
        device.credential_digest = credential_digest(owner.pk, credential.key)
        device.last_seen_at = timezone.now()
        device.save()
    return device_payload(device)


def unregister_device(user, installation_id):
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        PushDevice.objects.filter(user=user, installation_id=installation_id).update(
            is_active=False, marketing_opt_in=False, token_ciphertext='', token_digest=None,
            registration_scope=uuid.uuid4())


def deactivate_user_devices(user):
    PushDevice.objects.filter(user=user).update(is_active=False, token_ciphertext='', token_digest=None,
        credential_digest='', registration_scope=uuid.uuid4())
