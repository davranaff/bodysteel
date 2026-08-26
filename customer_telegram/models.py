from django.conf import settings
from django.db import models
from django.db.models import Q


class CustomerTelegramChat(models.Model):
    LANGUAGE_CHOICES = (('ru', 'Русский'), ('uz', "O‘zbekcha"))

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='customer_telegram_chat',
        verbose_name='Пользователь сайта',
    )
    telegram_user_id = models.BigIntegerField(unique=True, verbose_name='ID пользователя Telegram')
    chat_id = models.BigIntegerField(unique=True, verbose_name='ID чата Telegram')
    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        blank=True,
        default='',
        verbose_name='Язык',
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Бот активен')
    marketing_opt_in = models.BooleanField(default=False, db_index=True, verbose_name='Согласен на рассылки')
    marketing_consent_source = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name='Источник согласия на рассылки',
    )
    marketing_opted_in_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата согласия на рассылки')
    marketing_opted_out_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата отказа от рассылок')
    linked_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата привязки аккаунта')
    blocked_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата блокировки бота')
    last_seen_at = models.DateTimeField(null=True, blank=True, verbose_name='Последняя активность')
    marketing_next_send_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Следующую рассылку можно отправить после',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Telegram-клиент'
        verbose_name_plural = 'Telegram-клиенты'
        constraints = [models.CheckConstraint(condition=Q(telegram_user_id=models.F('chat_id'), telegram_user_id__gt=0), name='customer_tg_private_chat_identity')]

    def __str__(self):
        return 'Telegram-клиент #{}'.format(self.pk or 'новый')


class CustomerTelegramLink(models.Model):
    REGISTRATION = 'registration_otp'
    PASSWORD_RESET = 'password_reset_otp'
    ACCOUNT_LINK = 'account_link'
    PURPOSE_CHOICES = (
        (REGISTRATION, 'Код регистрации'),
        (PASSWORD_RESET, 'Код сброса пароля'),
        (ACCOUNT_LINK, 'Привязка аккаунта'),
    )
    AWAITING_START = 'awaiting_start'
    AWAITING_CONTACT = 'awaiting_contact'
    DELIVERING = 'delivering'
    DELIVERED = 'delivered'
    CONSUMED = 'consumed'
    LOCKED = 'locked'
    EXPIRED = 'expired'
    FAILED = 'failed'
    STATE_CHOICES = (
        (AWAITING_START, 'Ожидает запуска бота'),
        (AWAITING_CONTACT, 'Ожидает отправки контакта'),
        (DELIVERING, 'Отправляется'),
        (DELIVERED, 'Доставлен'),
        (CONSUMED, 'Использован'),
        (LOCKED, 'Заблокирован'),
        (EXPIRED, 'Истёк'),
        (FAILED, 'Ошибка'),
    )

    token_digest = models.CharField(max_length=64, unique=True, editable=False, verbose_name='Хеш токена')
    purpose = models.CharField(max_length=24, choices=PURPOSE_CHOICES, verbose_name='Назначение')
    registration_challenge = models.OneToOneField(
        'users.PhoneVerificationChallenge',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='customer_telegram_link',
        verbose_name='Запрос подтверждения регистрации',
    )
    auth_challenge = models.OneToOneField(
        'users.AuthChallenge',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='customer_telegram_link',
        verbose_name='Запрос подтверждения аккаунта',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='customer_telegram_links',
        verbose_name='Пользователь сайта',
    )
    chat = models.ForeignKey(
        CustomerTelegramChat,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='links',
        verbose_name='Telegram-клиент',
    )
    language = models.CharField(
        max_length=2,
        choices=CustomerTelegramChat.LANGUAGE_CHOICES,
        verbose_name='Язык',
    )
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=AWAITING_START, verbose_name='Состояние')
    contact_attempts_remaining = models.PositiveSmallIntegerField(default=3, verbose_name='Осталось попыток отправки контакта')
    expires_at = models.DateTimeField(db_index=True, verbose_name='Действует до')
    consumed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата использования')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(purpose='registration_otp', registration_challenge__isnull=False,
                      auth_challenge__isnull=True, user__isnull=True)
                    | Q(purpose='password_reset_otp', registration_challenge__isnull=True,
                        auth_challenge__isnull=False, user__isnull=True)
                    | Q(purpose='account_link', registration_challenge__isnull=True,
                        auth_challenge__isnull=True, user__isnull=False)
                ),
                name='customer_tg_link_exact_target',
            ),
            models.CheckConstraint(
                condition=Q(contact_attempts_remaining__gte=0), name='customer_tg_contact_attempts_gte_0',
            ),
        ]
        verbose_name = 'Связь Telegram с аккаунтом'
        verbose_name_plural = 'Связи Telegram с аккаунтами'


class CustomerTelegramUpdate(models.Model):
    update_id = models.BigIntegerField(unique=True, verbose_name='ID обновления Telegram')
    update_type = models.CharField(max_length=32, verbose_name='Тип обновления')
    status = models.CharField(max_length=16, default='processing', verbose_name='Статус обработки')
    failure_code = models.CharField(max_length=64, blank=True, default='', verbose_name='Код ошибки')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата получения')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата обработки')

    class Meta:
        verbose_name = 'Обновление от Telegram'
        verbose_name_plural = 'Обновления от Telegram'


# Campaign delivery models live separately to keep this model module focused.
from customer_telegram.campaign_models import (  # noqa: E402,F401
    CustomerTelegramCampaign,
    CustomerTelegramCampaignRecipient,
)
