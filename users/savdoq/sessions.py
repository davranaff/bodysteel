import hashlib
import hmac
import logging
from datetime import timedelta, timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.utils import timezone

from users.savdoq.client import (
    IssuedSession,
    SavdoqShopperClient,
    SavdoqUnavailable,
)
from users.savdoq.configuration import (
    SavdoqShopperConfigurationError,
    require_configuration,
    shopper_chat_configured,
)
from users.savdoq.models import SavdoqShopperSession


logger = logging.getLogger('bodysteel.savdoq')
REUSE_MARGIN = timedelta(seconds=30)


class ShopperSessionService:
    def __init__(self, configuration, client):
        self.configuration = configuration
        self.client = client

    def issue(self, user, credential, language, fresh=False):
        """Return a SAVDOQ session for a verified customer.

        A non-fresh request reuses the stored session so the web widget stays
        on one conversation; ``fresh`` starts a new SAVDOQ conversation.
        """
        digest = credential_digest(credential)
        if not fresh:
            stored = SavdoqShopperSession.objects.filter(
                user=user,
                language=language,
                credential_digest=digest,
                expires_at__gt=timezone.now() + REUSE_MARGIN,
            ).first()
            if stored is not None:
                return IssuedSession(stored.access_token, stored.expires_at, stored.session_id)
        issued = self.client.issue(subject_hash(self.configuration, user.pk), language)
        try:
            with transaction.atomic():
                SavdoqShopperSession.objects.update_or_create(
                    user=user,
                    language=language,
                    defaults={
                        'credential_digest': digest,
                        'access_token': issued.access_token,
                        'session_id': issued.session_id,
                        'expires_at': issued.expires_at,
                    },
                )
        except IntegrityError:
            # A concurrent request stored its own session; this one is still valid.
            pass
        return issued

    def revoke(self, user):
        SavdoqShopperSession.objects.filter(user=user).delete()
        self.client.revoke(subject_hash(self.configuration, user.pk))


def shopper_session_service():
    configuration = require_configuration()
    return ShopperSessionService(configuration, SavdoqShopperClient(configuration))


class ShopperChatRevocationFailed(Exception):
    pass


def revoke_shopper_chat(user):
    """Revoke every SAVDOQ session of a customer before sign-out or account changes.

    Raises ShopperChatRevocationFailed so callers never report a sign-out as
    complete while SAVDOQ may still accept the customer's chat sessions.
    """
    if not shopper_chat_configured():
        SavdoqShopperSession.objects.filter(user=user).delete()
        return
    try:
        shopper_session_service().revoke(user)
    except (SavdoqShopperConfigurationError, SavdoqUnavailable):
        logger.warning('savdoq_shopper_event=revoke outcome=failed user_id=%s', user.pk)
        raise ShopperChatRevocationFailed() from None
    logger.info('savdoq_shopper_event=revoke outcome=success user_id=%s', user.pk)


def subject_hash(configuration, user_id):
    # Must stay identical to the former storefront bridge, or customers lose
    # their SAVDOQ chat history: HMAC-SHA256("bodysteel:v1:<id>").
    message = f'{configuration.issuer}:v1:{user_id}'.encode('utf-8')
    return hmac.new(configuration.identity_key, message, hashlib.sha256).hexdigest()


def credential_digest(credential):
    return hashlib.sha256(credential.key.encode('utf-8')).hexdigest()


def session_payload(issued: IssuedSession):
    expires_at = issued.expires_at.astimezone(dt_timezone.utc)
    payload = {
        'accessToken': issued.access_token,
        'tokenType': 'Bearer',
        'expiresAt': expires_at.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        'shopperAuthenticated': True,
        'persistent': True,
    }
    if issued.session_id is not None:
        payload['sessionId'] = str(issued.session_id)
    return payload
