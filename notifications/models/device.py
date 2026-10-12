import uuid

from django.conf import settings
from django.db import models


class PushDevice(models.Model):
    class Platform(models.TextChoices):
        ANDROID = 'android', 'Android'
        IOS = 'ios', 'iOS'

    class Permission(models.TextChoices):
        AUTHORIZED = 'authorized', 'Разрешены'
        PROVISIONAL = 'provisional', 'Тихие уведомления'
        DENIED = 'denied', 'Запрещены'
        NOT_DETERMINED = 'not_determined', 'Не запрошены'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    installation_id = models.UUIDField(unique=True, editable=False, verbose_name='ID установки')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_devices', verbose_name='Пользователь')
    registration_scope = models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='Область привязки аккаунта')
    platform = models.CharField(max_length=7, choices=Platform.choices, db_index=True, verbose_name='Платформа')
    model = models.CharField(max_length=100, blank=True, default='', verbose_name='Модель устройства')
    os_version = models.CharField(max_length=40, blank=True, default='', verbose_name='Версия ОС')
    app_version = models.CharField(max_length=40, blank=True, default='', verbose_name='Версия приложения')
    app_build = models.CharField(max_length=40, blank=True, default='', verbose_name='Номер сборки')
    language = models.CharField(max_length=2, choices=(('ru', 'Русский'), ('uz', 'Узбекский')), verbose_name='Язык')
    permission = models.CharField(max_length=16, choices=Permission.choices, verbose_name='Разрешение ОС')
    marketing_opt_in = models.BooleanField(default=False, verbose_name='Согласие на рассылки')
    is_active = models.BooleanField(default=False, db_index=True, verbose_name='Активно')
    token_ciphertext = models.TextField(blank=True, default='', editable=False, verbose_name='Зашифрованный адрес доставки')
    token_digest = models.CharField(max_length=64, null=True, unique=True, editable=False, verbose_name='Отпечаток адреса доставки')
    credential_digest = models.CharField(max_length=64, blank=True, default='', editable=False, verbose_name='Отпечаток сессии')
    last_seen_at = models.DateTimeField(db_index=True, verbose_name='Последняя активность')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Push-устройство'
        verbose_name_plural = 'Push-устройства'
        indexes = [models.Index(fields=('user', 'is_active'), name='push_device_user_active')]

    def __str__(self):
        return '{} / {}'.format(self.platform, self.model or str(self.pk)[:8])
