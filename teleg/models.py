from django.db import models

from store.models import BaseModel


# Create your models here.

class SecretPhrase(BaseModel):
    phrase = models.CharField(max_length=20, unique=True)
    expired_date = models.DateTimeField()

    def __str__(self):
        return self.phrase

    class Meta:
        verbose_name = 'Секретный Ключ'
        verbose_name_plural = 'Секретные Ключи'


class Chat(BaseModel):
    chat_id = models.IntegerField()
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True)
    username = models.CharField(max_length=255, null=True)

    def __str__(self):
        return f"{self.chat_id}: {self.first_name}"

    class Meta:
        verbose_name = 'Чат'
        verbose_name_plural = 'Чаты'
