from dataclasses import dataclass
from datetime import timedelta
import time

import firebase_admin
from firebase_admin import exceptions, messaging
from django.conf import settings
from google.auth.exceptions import DefaultCredentialsError

from notifications.configuration import require_provider_configuration


@dataclass(frozen=True)
class SendResult:
    outcome: str
    code: str = ''
    message_id: str = ''
    retry_after: int = 60


class FirebaseSender:
    def send(self, token, delivery):
        require_provider_configuration()
        try:
            app = firebase_admin.get_app('bodysteel-push')
        except ValueError:
            # GOOGLE_APPLICATION_CREDENTIALS or workload identity stays server-side.
            try:
                app = firebase_admin.initialize_app(options={
                    'projectId': settings.PUSH_FIREBASE_PROJECT_ID, 'httpTimeout': 15,
                }, name='bodysteel-push')
            except (DefaultCredentialsError, OSError, ValueError):
                return SendResult('failed', code='provider_credentials')
        message = messaging.Message(
            token=token, notification=messaging.Notification(title=delivery.title, body=delivery.body),
            data={'notification_id': str(delivery.pk), 'scope': str(delivery.expected_scope), 'url': delivery.target_url},
            android=messaging.AndroidConfig(priority='high', ttl=timedelta(days=1),
                collapse_key=str(delivery.campaign_id), notification=messaging.AndroidNotification(
                    channel_id='bodysteel_notifications', tag=str(delivery.pk), sound='default')),
            apns=messaging.APNSConfig(headers={
                'apns-push-type': 'alert', 'apns-priority': '10', 'apns-collapse-id': str(delivery.pk),
                'apns-expiration': str(int(time.time()) + 86400),
            }, payload=messaging.APNSPayload(messaging.Aps(sound='default'))),
        )
        try:
            return SendResult('accepted', message_id=messaging.send(message, app=app))
        except messaging.UnregisteredError:
            return SendResult('invalid_token', code='unregistered')
        except messaging.QuotaExceededError:
            return SendResult('retry', code='quota_exceeded', retry_after=120)
        except (exceptions.UnavailableError, exceptions.InternalError, exceptions.DeadlineExceededError):
            return SendResult('retry', code='provider_unavailable')
        except messaging.SenderIdMismatchError:
            return SendResult('failed', code='provider_rejected')
        except (exceptions.UnauthenticatedError, exceptions.PermissionDeniedError):
            return SendResult('failed', code='provider_credentials')
        except (exceptions.InvalidArgumentError, ValueError, DefaultCredentialsError):
            return SendResult('failed', code='provider_rejected')
