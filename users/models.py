from django.contrib.auth.models import AbstractUser
from django.db import models

from users.utils.random_username import random_username
from users.validators import phone


class User(AbstractUser):

    username = models.CharField(max_length=100, unique=True, verbose_name='Имя пользователя')
    email = models.EmailField(unique=True, verbose_name='Электронная почта')
    phone = models.CharField(
        max_length=13,
        verbose_name='Номер телефона',
        unique=True,
        validators=[phone.validate_phone]
    )
    bonus_used = models.BooleanField(default=False, verbose_name='Бонус уже использован')
    phone_verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Телефон подтверждён')
    email_verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Почта подтверждена')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата удаления аккаунта')

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = random_username()
        return super().save(*args, **kwargs)

    def __str__(self):
        return '{0} {1} / {2}'.format(self.last_name, self.first_name, self.username)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


# Django discovers models through this module. Implementations stay in the auth feature.
from users.auth.models import (  # noqa: E402,F401
    AuthChallenge,
    AuthRateLimit,
    PhoneVerificationChallenge,
)
