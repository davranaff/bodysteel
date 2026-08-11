import uuid

from django.db import models
from django.utils import timezone


def webhook_event_id():
    return 'event_{}'.format(uuid.uuid4().hex)


class IntegrationCart(models.Model):
    CHANNEL_CHOICES = (('web', 'Web'), ('telegram', 'Telegram'))
    LANGUAGE_CHOICES = (('ru', 'Russian'), ('uz', 'Uzbek'))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_digest = models.CharField(max_length=64, unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    restore_token = models.CharField(max_length=64, unique=True, editable=False)
    items = models.JSONField()
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    ai_session_id = models.CharField(max_length=200)
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return str(self.id)


class IntegrationOrderAttribution(models.Model):
    order = models.OneToOneField(
        'store.Order',
        on_delete=models.CASCADE,
        related_name='savdoq_attribution',
    )
    cart = models.OneToOneField(
        IntegrationCart,
        on_delete=models.SET_NULL,
        related_name='order_attribution',
        null=True,
        blank=True,
    )
    ai_session_id = models.CharField(max_length=200)
    channel = models.CharField(max_length=16, choices=IntegrationCart.CHANNEL_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.order_id)


class IntegrationWebhookEvent(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('delivering', 'Delivering'),
        ('retry', 'Retry'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    )

    event_id = models.CharField(primary_key=True, max_length=200, default=webhook_event_id, editable=False)
    event_type = models.CharField(max_length=32, editable=False)
    body = models.TextField(editable=False)
    occurred_at = models.DateTimeField(editable=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_token = models.CharField(max_length=64, null=True, blank=True, editable=False)
    locked_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    failure_code = models.CharField(max_length=32, blank=True, default='')
    delivered_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('next_attempt_at', 'created_at')
        indexes = [
            models.Index(
                fields=('status', 'next_attempt_at'),
                name='integration_webhook_due_idx',
            ),
        ]

    def __str__(self):
        return self.event_id


class RegosWebhookEvent(models.Model):
    """Durable inbound queue for callbacks sent by a REGOS local integration."""

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_RETRY = 'retry'
    STATUS_DONE = 'done'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_RETRY, 'Retry'),
        (STATUS_DONE, 'Done'),
    )

    event_id = models.CharField(max_length=128, unique=True, editable=False)
    event_type = models.CharField(max_length=64, editable=False)
    item_id = models.PositiveBigIntegerField(null=True, blank=True, editable=False)
    payload = models.JSONField(editable=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_error = models.CharField(max_length=255, blank=True, default='')
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('next_attempt_at', 'created_at')
        indexes = [
            models.Index(fields=('status', 'next_attempt_at'), name='regos_webhook_due_idx'),
        ]

    def __str__(self):
        return self.event_id
