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

    order = models.ForeignKey(
        'store.Order',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name='Заказ',
    )
    course_purchase = models.ForeignKey(
        'courses.CoursePurchase',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name='Покупка курса',
    )
    provider = models.CharField(max_length=40, default='manual', db_index=True, verbose_name='Платёжная система')
    provider_payment_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        verbose_name='ID платежа в платёжной системе',
    )
    amount = models.PositiveBigIntegerField(verbose_name='Сумма')
    currency = models.CharField(max_length=3, default='UZS', verbose_name='Валюта')
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=CREATED,
        db_index=True,
        verbose_name='Статус',
    )
    idempotency_digest = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Ключ защиты от дублирования',
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Служебные данные')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата оплаты')

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
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'

    def __str__(self):
        return '{} {} {}'.format(self.provider, self.amount, self.currency)


class PaymentEvent(models.Model):
    PROCESSING_STATUS_CHOICES = (
        ('received', 'Получено'),
        ('processed', 'Обработано'),
    )

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='events', verbose_name='Платёж')
    provider = models.CharField(max_length=40, verbose_name='Платёжная система')
    external_event_id = models.CharField(max_length=255, verbose_name='ID события в платёжной системе')
    event_type = models.CharField(max_length=100, verbose_name='Тип события')
    payload_hash = models.CharField(max_length=64, verbose_name='Хеш содержимого события')
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS_CHOICES,
        default='received',
        verbose_name='Статус обработки',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата получения')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('provider', 'external_event_id'),
                name='payment_event_provider_external_id',
            ),
        ]
        verbose_name = 'Событие платежа'
        verbose_name_plural = 'События платежей'
