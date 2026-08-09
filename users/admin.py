from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.html import format_html

from store.admin_site import bodysteel_admin_site
from users.models import User


@admin.register(User, site=bodysteel_admin_site)
class UserAdmin(DjangoUserAdmin):
    list_display = ('user_identity', 'phone', 'email', 'account_badge', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'phone', 'email')
    ordering = ('-date_joined',)
    list_select_related = ()
    readonly_fields = ('date_joined', 'last_login')
    fieldsets = (
        ('Профиль', {'fields': ('username', ('first_name', 'last_name'), 'email', 'phone')}),
        ('Доступ', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Сессия', {'classes': ('collapse',), 'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'phone', 'email', 'password1', 'password2', 'is_staff'),
        }),
    )

    @admin.display(description='Покупатель', ordering='username')
    def user_identity(self, obj):
        display_name = '{} {}'.format(obj.first_name, obj.last_name).strip() or obj.username
        return format_html(
            '<strong>{}</strong><br><span class="bs-subtle">@{}</span>',
            display_name,
            obj.username,
        )

    @admin.display(description='Аккаунт')
    def account_badge(self, obj):
        tone = 'success' if obj.is_active else 'danger'
        label = 'Активен' if obj.is_active else 'Отключён'
        return format_html('<span class="bs-status bs-status--{}">{}</span>', tone, label)
