from django.conf import settings
from cryptography.fernet import Fernet, MultiFernet


class PushNotConfigured(Exception):
    pass


def token_cipher():
    keys = getattr(settings, 'PUSH_TOKEN_ENCRYPTION_KEYS', ())
    if isinstance(keys, str):
        keys = tuple(key.strip() for key in keys.split(',') if key.strip())
    try:
        if not keys:
            raise ValueError()
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except (TypeError, ValueError):
        raise PushNotConfigured('Push token encryption is not configured') from None


def require_provider_configuration():
    if not getattr(settings, 'PUSH_ENABLED', False) or not getattr(settings, 'PUSH_FIREBASE_PROJECT_ID', ''):
        raise PushNotConfigured('Firebase messaging is not configured')
    token_cipher()
