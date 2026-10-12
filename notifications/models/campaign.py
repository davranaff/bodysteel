import uuid

from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models


class PushCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Черновик'
        QUEUED = 'queued', 'В очереди'
        SCHEDULED = 'scheduled', 'Запланирована'
        SENDING = 'sending', 'Отправляется'
        COMPLETED = 'completed', 'Завершена'
        CANCELLED = 'cancelled', 'Отменена'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, verbose_name='Название кампании')
    title_ru = models.CharField(max_length=140, verbose_name='Заголовок RU')
    title_uz = models.CharField(max_length=140, verbose_name='Заголовок UZ')
    body_ru = models.TextField(validators=[MaxLengthValidator(1500)], verbose_name='Текст RU')
    body_uz = models.TextField(validators=[MaxLengthValidator(1500)], verbose_name='Текст UZ')
    target_url = models.URLField(max_length=500, blank=True, default='', verbose_name='Страница в приложении')
    audience = models.JSONField(default=dict, blank=True, verbose_name='Фильтры аудитории')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True, verbose_name='Статус')
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='Отправить не раньше')
    audience_frozen_at = models.DateTimeField(null=True, blank=True, editable=False, verbose_name='Аудитория зафиксирована')
    recipient_count = models.PositiveIntegerField(default=0, editable=False, verbose_name='Устройств в рассылке')
    user_count = models.PositiveIntegerField(default=0, editable=False, verbose_name='Пользователей в рассылке')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='created_push_campaigns', editable=False, verbose_name='Создал')
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                     related_name='published_push_campaigns', editable=False, verbose_name='Запустил')
    completed_at = models.DateTimeField(null=True, blank=True, editable=False, verbose_name='Завершена')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлена')

    class Meta:
        verbose_name = 'Push-рассылка'
        verbose_name_plural = 'Push-рассылки'
        permissions = [('publish_pushcampaign', 'Может запускать push-рассылки'),
                       ('test_pushcampaign', 'Может отправлять тест push-рассылки'),
                       ('cancel_pushcampaign', 'Может отменять push-рассылки')]

    def clean(self):
        from notifications.policies.campaign import validate_campaign
        validate_campaign(self)

    def __str__(self):
        return self.name
