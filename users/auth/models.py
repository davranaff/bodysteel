import uuid

from django.conf import settings
from django.db import models


class PhoneVerificationChallenge(models.Model):
    class Status(models.TextChoices):
        AWAITING = 'awaiting', 'Awaiting Telegram'
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        UNKNOWN = 'unknown', 'Delivery unknown'
        FAILED = 'failed', 'Delivery failed'
        CONSUMED = 'consumed', 'Consumed'
        LOCKED = 'locked', 'Locked'

    class DeliveryChannel(models.TextChoices):
        SMS = 'sms', 'SMS'
        TELEGRAM = 'telegram', 'Telegram'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_id = models.UUIDField(default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254)
    phone = models.CharField(max_length=13, unique=True)
    username = models.CharField(max_length=100, blank=True, default='')
    first_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=150, blank=True, default='')
    code_digest = models.CharField(max_length=64)
    delivery_channel = models.CharField(
        max_length=10,
        choices=DeliveryChannel.choices,
        default=DeliveryChannel.SMS,
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts_remaining = models.PositiveSmallIntegerField(default=5)
    expires_at = models.DateTimeField()
    resend_after = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['expires_at'], name='users_otp_exp_idx'),
            models.Index(fields=['email'], name='users_otp_email_idx'),
        ]


class AuthChallenge(models.Model):
    class Kind(models.TextChoices):
        PASSWORD_RESET = 'password_reset', 'Password reset'
        EMAIL_VERIFICATION = 'email_verification', 'Email verification'
        PHONE_CHANGE = 'phone_change', 'Phone change'

    class Channel(models.TextChoices):
        SMS = 'sms', 'SMS'
        EMAIL = 'email', 'Email'
        TELEGRAM = 'telegram', 'Telegram'

    class Status(models.TextChoices):
        AWAITING = 'awaiting', 'Awaiting Telegram'
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        UNKNOWN = 'unknown', 'Delivery unknown'
        FAILED = 'failed', 'Delivery failed'
        CONSUMED = 'consumed', 'Consumed'
        LOCKED = 'locked', 'Locked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_id = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='auth_challenges',
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    identifier = models.CharField(max_length=254)
    code_digest = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts_remaining = models.PositiveSmallIntegerField(default=5)
    expires_at = models.DateTimeField()
    resend_after = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['kind', 'identifier'], name='users_auth_ch_kind_id_idx'),
            models.Index(fields=['expires_at'], name='users_auth_ch_exp_idx'),
        ]


class AuthRateLimit(models.Model):
    scope = models.CharField(max_length=40)
    subject_digest = models.CharField(max_length=64)
    window_started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['scope', 'subject_digest', 'window_started_at'],
                name='users_rate_scope_subject_window_uniq',
            ),
        ]
        indexes = [models.Index(fields=['expires_at'], name='users_rate_exp_idx')]
