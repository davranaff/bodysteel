from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from notifications.configuration import PushNotConfigured, require_provider_configuration
from notifications.forms import ACCOUNT_FIELDS, BASE_FIELDS, DEVICE_FIELDS, INTEREST_FIELDS, PURCHASE_FIELDS, PushCampaignForm
from notifications.models import PushCampaign, PushDelivery, PushDevice
from notifications.services.campaigns import cancel_campaign, preview_audience, publish_campaign, queue_test, save_draft
from store.admin_site import bodysteel_admin_site


@admin.register(PushCampaign, site=bodysteel_admin_site)
class PushCampaignAdmin(admin.ModelAdmin):
    form = PushCampaignForm
    change_form_template = 'admin/notifications/campaign_change.html'
    list_display = ('name', 'status', 'user_count', 'recipient_count', 'scheduled_at', 'created_at')
    list_filter = ('status', 'created_at', 'scheduled_at')
    search_fields = ('name', 'title_ru', 'title_uz')
    readonly_fields = ('status', 'user_count', 'recipient_count', 'audience_frozen_at', 'created_by', 'published_by', 'completed_at', 'audience')
    ordering = ('-created_at',)

    def get_form(self, request, obj=None, **kwargs):
        kwargs['fields'] = BASE_FIELDS
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        info = ('Результат', {'fields': self.readonly_fields})
        if obj and obj.status != 'draft':
            return (('Сообщение', {'fields': BASE_FIELDS}), info)
        return (
            ('Сообщение', {'fields': BASE_FIELDS, 'description': 'Текст без персональных данных. Возраст и вес не хранятся и не вычисляются.'}),
            ('Устройства', {'fields': DEVICE_FIELDS, 'description': 'Только разрешённые устройства с отдельным согласием на рассылки. Неактивные более 90 дней исключаются.'}),
            ('Аккаунты', {'fields': ACCOUNT_FIELDS, 'classes': ('collapse',)}),
            ('Покупки', {'fields': PURCHASE_FIELDS, 'classes': ('collapse',), 'description': 'Разные поля объединяются через И. Внутри списка — ИЛИ. Товары/категории/бренды должны совпасть в одной позиции. Последняя покупка — последняя среди выбранного типа заказов.'}),
            ('Корзина, избранное и обучение', {'fields': INTEREST_FIELDS, 'classes': ('collapse',)}), info,
        )

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (BASE_FIELDS if obj and obj.status != 'draft' else ())

    def save_model(self, request, obj, form, change):
        save_draft(obj, request.user)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except ValidationError:
            self.message_user(request, 'Кампания изменилась. Обновите страницу перед сохранением.', messages.ERROR)
            return HttpResponseRedirect(request.path)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (obj is None or obj.status == 'draft')

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (obj is None or (obj.status == 'draft' and not obj.deliveries.exists()))

    def get_urls(self):
        return [path('<uuid:campaign_id>/preview/', self.admin_site.admin_view(self.preview),
                     name='notifications_pushcampaign_preview')] + super().get_urls()

    def preview(self, request, campaign_id):
        from django.core.exceptions import PermissionDenied
        campaign = self.get_object(request, str(campaign_id))
        if campaign is None or not self.has_view_or_change_permission(request, campaign):
            raise PermissionDenied()
        if request.method == 'POST':
            try:
                action = request.POST.get('operation')
                if action == 'publish':
                    try:
                        expected = int(request.POST.get('expected_devices', ''))
                    except ValueError:
                        raise ValidationError('Обновите предпросмотр перед подтверждением.') from None
                    publish_campaign(campaign.pk, request.user, expected)
                elif action == 'cancel':
                    cancel_campaign(campaign.pk, request.user)
                elif action == 'test':
                    queue_test(campaign.pk, request.POST.get('test_device'), request.user)
                else:
                    raise ValidationError('Неизвестное действие.')
                self.log_change(request, campaign, 'Push operation: ' + action)
                self.message_user(request, 'Действие сохранено. Отправку выполняет worker, не браузер.')
                return HttpResponseRedirect(reverse('admin:notifications_pushcampaign_change', args=[campaign.pk]))
            except (ValidationError, PushNotConfigured):
                self.message_user(request, 'Не удалось выполнить действие. Проверьте Firebase, аудиторию и статус кампании.', messages.ERROR)
            campaign.refresh_from_db()
        size = preview_audience(campaign) if campaign.status == 'draft' else None
        ready = True
        try:
            require_provider_configuration()
        except PushNotConfigured:
            ready = False
        counts = dict(campaign.deliveries.filter(is_test=False).values_list('status').annotate(total=Count('pk')))
        totals = {label: counts.get(status, 0) for status, label in PushDelivery.Status.choices}
        return TemplateResponse(request, 'admin/notifications/campaign_preview.html', {
            **self.admin_site.each_context(request), 'title': 'Push: аудитория и подтверждение', 'opts': self.model._meta,
            'campaign': campaign, 'size': size, 'totals': totals, 'provider_ready': ready,
            'can_publish': request.user.has_perm('notifications.publish_pushcampaign'),
            'can_cancel': request.user.has_perm('notifications.cancel_pushcampaign'),
            'can_test': request.user.has_perm('notifications.test_pushcampaign'),
            'test_devices': PushDevice.objects.filter(user=request.user, is_active=True),
        })


@admin.register(PushDevice, site=bodysteel_admin_site)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'platform', 'model', 'os_version', 'app_version', 'language', 'permission', 'marketing_opt_in', 'is_active', 'last_seen_at')
    list_filter = ('platform', 'language', 'permission', 'marketing_opt_in', 'is_active', 'last_seen_at')
    search_fields = ('user__username', 'model', 'app_version', 'os_version')
    list_select_related = ('user',)
    exclude = ('token_ciphertext', 'token_digest', 'credential_digest')
    readonly_fields = tuple(field.name for field in PushDevice._meta.fields
                            if field.name not in ('token_ciphertext', 'token_digest', 'credential_digest'))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PushDelivery, site=bodysteel_admin_site)
class PushDeliveryAdmin(admin.ModelAdmin):
    list_display = ('kind', 'campaign', 'order_code', 'order_event', 'device', 'language', 'status', 'is_test',
                    'attempt_count', 'failure_code', 'accepted_at')
    list_filter = ('kind', 'status', 'order_event', 'is_test', 'language', 'created_at')
    list_select_related = ('campaign', 'order', 'device', 'user')
    search_fields = ('order__order_code',)
    exclude = ('dedupe_key', 'order')
    readonly_fields = tuple(field.name for field in PushDelivery._meta.fields
                            if field.name not in ('dedupe_key', 'order')) + ('order_code',)

    @admin.display(description='Номер заказа', ordering='order__order_code')
    def order_code(self, obj):
        # Only the public code: the order's __str__ includes the recipient name.
        return obj.order.order_code if obj.order_id else '—'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
