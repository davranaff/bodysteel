from django.db import models
from django.contrib.auth.models import AbstractUser

from users.utils.random_code import random_code
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
    code = models.CharField(max_length=6, unique=True, null=True)
    verification = models.BooleanField(default=False)

    phone_idx = models.Index(fields=['phone'], name='phone_idx')

    def save(self, with_code=True, *args, **kwargs):
        if not self.username:
            self.username = random_username()
        if not self.code:
            self.code = random_code()
        if not with_code:
            self.code = None
        return super().save(*args, **kwargs)

    def __str__(self):
        return '{0} {1} / {2}'.format(self.last_name, self.first_name, self.username)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
