from django.db import models
from django.contrib.auth.models import AbstractUser
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

    phone_idx = models.Index(fields=['phone'], name='phone_idx')

    def __str__(self):
        return '{0} {1} / {2}'.format(self.last_name, self.first_name, self.username)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
