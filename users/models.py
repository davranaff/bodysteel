from django.contrib.auth.models import AbstractUser
from django.db import models

from users.utils.random_username import random_username
from users.validators import phone


class User(AbstractUser):

    username = models.CharField(max_length=100, unique=True, verbose_name='никнейм ползователя')
    email = models.EmailField(unique=True, verbose_name='Эл. Почта ползователя')
    phone = models.CharField(
        max_length=13,
        verbose_name='Телефон номер ползователя',
        unique=True,
        validators=[phone.validate_phone]
    )
    bonus_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = random_username()
        return super().save(*args, **kwargs)

    def __str__(self):
        return '{0} {1} / {2}'.format(self.last_name, self.first_name, self.username)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'


# Django discovers models through this module. Implementations stay in the auth feature.
from users.auth.models import AuthRateLimit, PhoneVerificationChallenge  # noqa: E402,F401
