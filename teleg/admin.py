from django.contrib import admin

from teleg.models import SecretPhrase, Chat

# Register your models here.

@admin.register(SecretPhrase)
class OrdersAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'phrase', 'expired_date',]
    list_editable = ['phrase', 'expired_date',]

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'chat_id', 'first_name', 'last_name', 'username',]
    list_editable = ['first_name', 'last_name', 'username',]
