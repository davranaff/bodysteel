from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models

from customer_telegram.models import CustomerTelegramChat


class CustomerTelegramCampaign(models.Model):
    DRAFT = 'draft'
    SCHEDULED = 'scheduled'
    QUEUEING = 'queueing'
    SENDING = 'sending'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'
    STATUS_CHOICES = (
        (DRAFT, 'Черновик'),
        (SCHEDULED, 'Запланирована'),
        (QUEUEING, 'Формируется очередь'),
        (SENDING, 'Отправляется'),
        (COMPLETED, 'Завершена'),
        (CANCELLED, 'Отменена'),
        (FAILED, 'Ошибка'),
    )

    name = models.CharField(max_length=120, verbose_name='Внутреннее название кампании')
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=DRAFT,
        db_index=True,
        verbose_name='Статус',
    )
    title_ru = models.CharField(max_length=200, verbose_name='Заголовок на русском')
    title_uz = models.CharField(max_length=200, verbose_name='Заголовок на узбекском')
    body_ru = models.TextField(validators=[MaxLengthValidator(3200)], verbose_name='Текст сообщения на русском')
    body_uz = models.TextField(validators=[MaxLengthValidator(3200)], verbose_name='Текст сообщения на узбекском')
    button_text_ru = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Текст кнопки на русском',
    )
    button_text_uz = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Текст кнопки на узбекском',
    )
    button_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        verbose_name='Ссылка кнопки',
        help_text='Допускаются только HTTPS-ссылки на сайт BodySteel.',
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Запланировать отправку на',
        help_text='Оставьте пустым, чтобы начать отправку сразу после подтверждения.',
    )
    audience_built_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата формирования аудитории')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='customer_telegram_campaigns',
        verbose_name='Создал',
    )
    test_recipient = models.ForeignKey(
        CustomerTelegramChat,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='test_campaigns',
        verbose_name='Получатель тестового сообщения',
    )
    recipient_count = models.PositiveIntegerField(default=0, verbose_name='Всего получателей')
    delivered_count = models.PositiveIntegerField(default=0, verbose_name='Доставлено')
    failed_count = models.PositiveIntegerField(default=0, verbose_name='Ошибок доставки')
    blocked_count = models.PositiveIntegerField(default=0, verbose_name='Заблокировали бота')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата начала отправки')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата завершения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        permissions = (
            ('test_customertelegramcampaign', 'Может отправлять тест клиентской Telegram-рассылки'),
            ('publish_customertelegramcampaign', 'Может запускать клиентскую Telegram-рассылку'),
        )
        verbose_name = 'Telegram-рассылка'
        verbose_name_plural = 'Telegram-рассылки'

    def clean(self):
        if bool(self.button_text_ru) != bool(self.button_text_uz):
            raise ValidationError('Необходимо заполнить текст кнопки на обоих языках.')
        if bool(self.button_text_ru) != bool(self.button_url):
            raise ValidationError('Текст кнопки и ссылку необходимо заполнять вместе.')
        if self.button_url:
            allowed = urlsplit(getattr(settings, 'CUSTOMER_TELEGRAM_STORE_ORIGIN', ''))
            candidate = urlsplit(self.button_url)
            if (
                candidate.scheme != 'https' or candidate.netloc != allowed.netloc
                or candidate.username or candidate.password or candidate.fragment
            ):
                raise ValidationError('Ссылка кампании должна вести на HTTPS-страницу сайта BodySteel.')

    def __str__(self):
        return self.name


class CustomerTelegramCampaignRecipient(models.Model):
    PENDING = 'pending'
    SENDING = 'sending'
    DELIVERED = 'delivered'
    RETRY = 'retry'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    BLOCKED = 'blocked'
    STATUS_CHOICES = (
        (PENDING, 'Ожидает отправки'),
        (SENDING, 'Отправляется'),
        (DELIVERED, 'Доставлено'),
        (RETRY, 'Ожидает повторной попытки'),
        (FAILED, 'Ошибка'),
        (SKIPPED, 'Пропущено'),
        (BLOCKED, 'Бот заблокирован'),
    )

    campaign = models.ForeignKey(
        CustomerTelegramCampaign,
        on_delete=models.CASCADE,
        related_name='recipients',
        verbose_name='Кампания',
    )
    chat = models.ForeignKey(
        CustomerTelegramChat,
        on_delete=models.CASCADE,
        related_name='campaign_deliveries',
        verbose_name='Telegram-клиент',
    )
    language = models.CharField(
        max_length=2,
        choices=CustomerTelegramChat.LANGUAGE_CHOICES,
        verbose_name='Язык сообщения',
    )
    rendered_title = models.CharField(max_length=200, verbose_name='Отправленный заголовок')
    rendered_body = models.TextField(max_length=3200, verbose_name='Отправленный текст')
    rendered_button_text = models.CharField(max_length=64, blank=True, default='', verbose_name='Текст кнопки')
    rendered_button_url = models.URLField(max_length=500, blank=True, default='', verbose_name='Ссылка кнопки')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING, verbose_name='Статус')
    attempt_count = models.PositiveSmallIntegerField(default=0, verbose_name='Количество попыток')
    next_attempt_at = models.DateTimeField(db_index=True, verbose_name='Следующая попытка')
    lease_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        editable=False,
        verbose_name='Токен обработки',
    )
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата блокировки на обработку')
    telegram_message_id = models.BigIntegerField(null=True, blank=True, verbose_name='ID сообщения Telegram')
    failure_code = models.CharField(max_length=64, blank=True, default='', verbose_name='Код ошибки')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата доставки')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('campaign', 'chat'), name='customer_tg_campaign_chat_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=('status', 'next_attempt_at'), name='customer_tg_delivery_due_idx'),
        ]
        verbose_name = 'Получатель Telegram-рассылки'
        verbose_name_plural = 'Получатели Telegram-рассылок'
