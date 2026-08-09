import uuid

from django.db import models


class PhoneVerificationChallenge(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        UNKNOWN = 'unknown', 'Delivery unknown'
        FAILED = 'failed', 'Delivery failed'
        CONSUMED = 'consumed', 'Consumed'
        LOCKED = 'locked', 'Locked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_id = models.UUIDField(default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254)
    phone = models.CharField(max_length=13, unique=True)
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
            models.Index(fields=['expires_at'], name='users_otp_exp_idx'),
            models.Index(fields=['email'], name='users_otp_email_idx'),
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
