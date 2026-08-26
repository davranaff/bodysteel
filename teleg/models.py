from django.db import models

from store.models import BaseModel


# Create your models here.

class SecretPhrase(BaseModel):
    phrase = models.CharField(max_length=20, unique=True, verbose_name='Секретный ключ')
    expired_date = models.DateTimeField(verbose_name='Действует до')

    def __str__(self):
        return self.phrase

    class Meta:
        verbose_name = 'Секретный Ключ'
        verbose_name_plural = 'Секретные Ключи'


class Chat(BaseModel):
    chat_id = models.CharField(max_length=255, verbose_name='ID чата')
    first_name = models.CharField(max_length=255, verbose_name='Имя')
    last_name = models.CharField(max_length=255, null=True, verbose_name='Фамилия')
    username = models.CharField(max_length=255, null=True, verbose_name='Имя пользователя Telegram')

    def __str__(self):
        return f"{self.chat_id}: {self.first_name}"

    class Meta:
        verbose_name = 'Чат'
        verbose_name_plural = 'Чаты'
