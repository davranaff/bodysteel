from django.contrib import admin
from django.utils.html import format_html

from store.admin_site import bodysteel_admin_site
from teleg.models import Chat, SecretPhrase


@admin.register(SecretPhrase, site=bodysteel_admin_site)
class SecretPhraseAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    list_display = ('phrase', 'expiry_badge', 'expired_date')
    search_fields = ('phrase',)
    list_filter = ('expired_date',)
    list_editable = ('expired_date',)

    @admin.display(description='Состояние')
    def expiry_badge(self, obj):
        from django.utils import timezone
        active = obj.expired_date > timezone.now()
        return format_html(
            '<span class="bs-status bs-status--{}">{}</span>',
            'success' if active else 'danger',
            'Активна' if active else 'Истекла',
        )


@admin.register(Chat, site=bodysteel_admin_site)
class ChatAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    list_display = ('chat_identity', 'username', 'last_name', 'created_at')
    search_fields = ('chat_id', 'first_name', 'last_name', 'username')
    date_hierarchy = 'created_at'
    readonly_fields = ('chat_id', 'created_at')

    @admin.display(description='Пользователь')
    def chat_identity(self, obj):
        return format_html('<strong>{}</strong><br><span class="bs-subtle">ID {}</span>', obj.first_name, obj.chat_id)
