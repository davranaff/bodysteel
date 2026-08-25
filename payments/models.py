from django.db import models


class Payment(models.Model):
    CREATED = 'created'
    PENDING = 'pending'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'
    STATUS_CHOICES = (
        (CREATED, 'Создан'),
        (PENDING, 'Ожидает оплаты'),
        (SUCCEEDED, 'Успешен'),
        (FAILED, 'Ошибка'),
        (CANCELLED, 'Отменён'),
        (REFUNDED, 'Возвращён'),
    )

    order = models.ForeignKey('store.Order', on_delete=models.PROTECT, null=True, blank=True, related_name='payments')
    course_purchase = models.ForeignKey(
        'courses.CoursePurchase', on_delete=models.PROTECT, null=True, blank=True, related_name='payments'
    )
    provider = models.CharField(max_length=40, default='manual', db_index=True)
    provider_payment_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    amount = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default='UZS')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=CREATED, db_index=True)
    idempotency_digest = models.CharField(max_length=64, unique=True, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(order__isnull=False, course_purchase__isnull=True)
                    | models.Q(order__isnull=True, course_purchase__isnull=False)
                ),
                name='payment_exactly_one_target',
            ),
        ]

    def __str__(self):
        return '{} {} {}'.format(self.provider, self.amount, self.currency)


class PaymentEvent(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='events')
    provider = models.CharField(max_length=40)
    external_event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=100)
    payload_hash = models.CharField(max_length=64)
    processing_status = models.CharField(max_length=20, default='received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('provider', 'external_event_id'),
                name='payment_event_provider_external_id',
            ),
        ]
