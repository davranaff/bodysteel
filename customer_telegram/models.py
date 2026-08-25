from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
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
    )
    telegram_user_id = models.BigIntegerField(unique=True)
    chat_id = models.BigIntegerField(unique=True)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    marketing_opt_in = models.BooleanField(default=False, db_index=True)
    marketing_consent_source = models.CharField(max_length=32, blank=True, default='')
    marketing_opted_in_at = models.DateTimeField(null=True, blank=True)
    marketing_opted_out_at = models.DateTimeField(null=True, blank=True)
    linked_at = models.DateTimeField(null=True, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    marketing_next_send_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Telegram-клиент'
        verbose_name_plural = 'Telegram-клиенты'
        constraints = [models.CheckConstraint(condition=Q(telegram_user_id=models.F('chat_id'), telegram_user_id__gt=0), name='customer_tg_private_chat_identity')]

    def __str__(self):
        return 'Telegram client #{}'.format(self.pk or 'new')


class CustomerTelegramLink(models.Model):
    REGISTRATION = 'registration_otp'
    PASSWORD_RESET = 'password_reset_otp'
    ACCOUNT_LINK = 'account_link'
    PURPOSE_CHOICES = (
        (REGISTRATION, 'Registration OTP'),
        (PASSWORD_RESET, 'Password reset OTP'),
        (ACCOUNT_LINK, 'Account link'),
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
        (AWAITING_START, 'Awaiting start'),
        (AWAITING_CONTACT, 'Awaiting contact'),
        (DELIVERING, 'Delivering'),
        (DELIVERED, 'Delivered'),
        (CONSUMED, 'Consumed'),
        (LOCKED, 'Locked'),
        (EXPIRED, 'Expired'),
        (FAILED, 'Failed'),
    )

    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    purpose = models.CharField(max_length=24, choices=PURPOSE_CHOICES)
    registration_challenge = models.OneToOneField(
        'users.PhoneVerificationChallenge',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='customer_telegram_link',
    )
    auth_challenge = models.OneToOneField(
        'users.AuthChallenge',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='customer_telegram_link',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='customer_telegram_links',
    )
    chat = models.ForeignKey(
        CustomerTelegramChat,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='links',
    )
    language = models.CharField(max_length=2, choices=CustomerTelegramChat.LANGUAGE_CHOICES)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=AWAITING_START)
    contact_attempts_remaining = models.PositiveSmallIntegerField(default=3)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


class CustomerTelegramUpdate(models.Model):
    update_id = models.BigIntegerField(unique=True)
    update_type = models.CharField(max_length=32)
    status = models.CharField(max_length=16, default='processing')
    failure_code = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)


class CustomerTelegramCampaign(models.Model):
    DRAFT = 'draft'
    SCHEDULED = 'scheduled'
    QUEUEING = 'queueing'
    SENDING = 'sending'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'
    STATUS_CHOICES = tuple((value, value.title()) for value in (
        DRAFT, SCHEDULED, QUEUEING, SENDING, COMPLETED, CANCELLED, FAILED,
    ))

    name = models.CharField(max_length=120)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT, db_index=True)
    title_ru = models.CharField(max_length=200)
    title_uz = models.CharField(max_length=200)
    body_ru = models.TextField(validators=[MaxLengthValidator(3200)])
    body_uz = models.TextField(validators=[MaxLengthValidator(3200)])
    button_text_ru = models.CharField(max_length=64, blank=True, default='')
    button_text_uz = models.CharField(max_length=64, blank=True, default='')
    button_url = models.URLField(max_length=500, blank=True, default='')
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    audience_built_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='customer_telegram_campaigns',
    )
    test_recipient = models.ForeignKey(
        CustomerTelegramChat,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='test_campaigns',
    )
    recipient_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    blocked_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = (
            ('test_customertelegramcampaign', 'Can test customer Telegram campaign'),
            ('publish_customertelegramcampaign', 'Can publish customer Telegram campaign'),
        )

    def clean(self):
        if bool(self.button_text_ru) != bool(self.button_text_uz):
            raise ValidationError('Both button translations are required.')
        if bool(self.button_text_ru) != bool(self.button_url):
            raise ValidationError('Button text and URL must be configured together.')
        if self.button_url:
            allowed = urlsplit(getattr(settings, 'CUSTOMER_TELEGRAM_STORE_ORIGIN', ''))
            candidate = urlsplit(self.button_url)
            if (
                candidate.scheme != 'https' or candidate.netloc != allowed.netloc
                or candidate.username or candidate.password or candidate.fragment
            ):
                raise ValidationError('Campaign URL must use the BodySteel HTTPS origin.')

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
    STATUS_CHOICES = tuple((value, value.title()) for value in (
        PENDING, SENDING, DELIVERED, RETRY, FAILED, SKIPPED, BLOCKED,
    ))

    campaign = models.ForeignKey(
        CustomerTelegramCampaign, on_delete=models.CASCADE, related_name='recipients',
    )
    chat = models.ForeignKey(
        CustomerTelegramChat, on_delete=models.CASCADE, related_name='campaign_deliveries',
    )
    language = models.CharField(max_length=2, choices=CustomerTelegramChat.LANGUAGE_CHOICES)
    rendered_title = models.CharField(max_length=200)
    rendered_body = models.TextField(max_length=3200)
    rendered_button_text = models.CharField(max_length=64, blank=True, default='')
    rendered_button_url = models.URLField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(db_index=True)
    lease_token = models.CharField(max_length=64, null=True, blank=True, editable=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    telegram_message_id = models.BigIntegerField(null=True, blank=True)
    failure_code = models.CharField(max_length=64, blank=True, default='')
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('campaign', 'chat'), name='customer_tg_campaign_chat_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=('status', 'next_attempt_at'), name='customer_tg_delivery_due_idx'),
        ]
