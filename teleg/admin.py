from django.contrib import admin

from teleg.models import SecretPhrase

# Register your models here.

@admin.register(SecretPhrase)
class OrdersAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'phrase', 'expired_date',]
    list_editable = ['phrase', 'expired_date',]