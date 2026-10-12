import uuid

from django.conf import settings
from django.db import models


class PushDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'В очереди'
        SENDING = 'sending', 'Отправляется'
        ACCEPTED = 'accepted', 'Принято Firebase'
        RETRY = 'retry', 'Повтор позже'
        FAILED = 'failed', 'Ошибка'
        SKIPPED = 'skipped', 'Пропущено'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey('notifications.PushCampaign', on_delete=models.PROTECT, related_name='deliveries', verbose_name='Кампания')
    device = models.ForeignKey('notifications.PushDevice', null=True, on_delete=models.SET_NULL,
                              related_name='deliveries', verbose_name='Устройство')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                            related_name='push_deliveries', verbose_name='Пользователь')
    expected_scope = models.UUIDField(editable=False, verbose_name='Ожидаемая область аккаунта')
    language = models.CharField(max_length=2, verbose_name='Язык')
    title = models.CharField(max_length=140, verbose_name='Заголовок')
    body = models.TextField(max_length=1500, verbose_name='Текст')
    target_url = models.URLField(max_length=500, blank=True, default='', verbose_name='Страница приложения')
    is_test = models.BooleanField(default=False, verbose_name='Тестовая отправка')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                     related_name='requested_push_deliveries', editable=False, verbose_name='Запросил')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name='Статус')
    attempt_count = models.PositiveSmallIntegerField(default=0, verbose_name='Попыток')
    next_attempt_at = models.DateTimeField(db_index=True, verbose_name='Следующая попытка')
    lease_token = models.UUIDField(null=True, editable=False, verbose_name='Аренда обработки')
    locked_at = models.DateTimeField(null=True, editable=False, verbose_name='Начало обработки')
    accepted_at = models.DateTimeField(null=True, verbose_name='Принято Firebase')
    failure_code = models.CharField(max_length=40, blank=True, default='', verbose_name='Код ошибки')
    provider_message_id = models.CharField(max_length=255, blank=True, default='', editable=False, verbose_name='ID сообщения провайдера')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    class Meta:
        verbose_name = 'Отправка push'
        verbose_name_plural = 'Отправки push'
        constraints = [models.UniqueConstraint(fields=('campaign', 'device'),
                         condition=models.Q(is_test=False), name='push_campaign_device_unique')]
        indexes = [models.Index(fields=('status', 'next_attempt_at'), name='push_delivery_due')]
