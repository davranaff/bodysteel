from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from customer_telegram.campaigns import send_test_campaign
from customer_telegram.models import (
    CustomerTelegramCampaign,
    CustomerTelegramCampaignRecipient,
    CustomerTelegramChat,
)
from store.admin_site import bodysteel_admin_site


@admin.register(CustomerTelegramChat, site=bodysteel_admin_site)
class CustomerTelegramChatAdmin(admin.ModelAdmin):
    list_display = (
        'internal_identity', 'linked', 'user', 'language', 'is_active', 'marketing_opt_in',
        'linked_at', 'last_seen_at',
    )
    list_filter = ('language', 'is_active', 'marketing_opt_in', 'blocked_at')
    search_fields = ('id', 'user__username', 'user__email')
    list_select_related = ('user',)
    readonly_fields = (
        'telegram_user_id', 'chat_id', 'user', 'linked_at', 'blocked_at',
        'last_seen_at', 'created_at', 'updated_at', 'marketing_opted_in_at',
        'marketing_opted_out_at', 'marketing_consent_source', 'marketing_next_send_at',
    )

    @admin.display(description='Telegram-клиент')
    def internal_identity(self, obj):
        return 'Клиент #{}'.format(obj.pk)

    @admin.display(boolean=True, description='Привязан')
    def linked(self, obj):
        return obj.user_id is not None


@admin.register(CustomerTelegramCampaign, site=bodysteel_admin_site)
class CustomerTelegramCampaignAdmin(admin.ModelAdmin):
    change_form_template = 'admin/customer_telegram/customertelegramcampaign/change_form.html'
    list_display = (
        'name', 'status', 'scheduled_at', 'recipient_count', 'delivered_count',
        'retry_count', 'failed_count', 'blocked_count', 'created_by', 'created_at',
    )
    list_filter = ('status', 'scheduled_at', 'created_at')
    search_fields = ('name', 'title_ru', 'title_uz')
    readonly_fields = (
        'status', 'preview_ru', 'preview_uz', 'recipient_count', 'delivered_count',
        'failed_count', 'blocked_count', 'audience_built_at', 'started_at',
        'completed_at', 'created_at', 'updated_at',
    )
    actions = ('publish_campaigns', 'test_campaigns', 'cancel_campaigns')
    fieldsets = (
        ('Кампания', {'fields': ('name', 'status', 'scheduled_at', 'test_recipient')}),
        ('Русский', {'fields': ('title_ru', 'body_ru', 'button_text_ru', 'preview_ru')}),
        ('O‘zbekcha', {'fields': ('title_uz', 'body_uz', 'button_text_uz', 'preview_uz')}),
        ('Кнопка', {'fields': ('button_url',)}),
        ('Статистика', {'fields': (
            'recipient_count', 'delivered_count', 'failed_count', 'blocked_count',
            'audience_built_at', 'started_at', 'completed_at', 'created_at', 'updated_at',
        )}),
    )

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path(
                '<path:object_id>/publish/',
                self.admin_site.admin_view(self.publish_campaign_view),
                name='{}_{}_publish'.format(*info),
            ),
        ]
        return custom_urls + super().get_urls()

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        context = dict(extra_context or {})
        campaign = self.get_object(request, unquote(object_id)) if object_id else None
        if (
            campaign
            and campaign.status == CustomerTelegramCampaign.DRAFT
            and request.user.has_perm('customer_telegram.publish_customertelegramcampaign')
        ):
            info = self.model._meta.app_label, self.model._meta.model_name
            context['campaign_publish_url'] = reverse(
                '{}:{}_{}_publish'.format(self.admin_site.name, *info),
                args=(campaign.pk,),
            )
        return super().changeform_view(request, object_id, form_url, context)

    def publish_campaign_view(self, request, object_id):
        campaign = self.get_object(request, unquote(object_id))
        if campaign is None:
            raise Http404
        if (
            not self.has_change_permission(request, campaign)
            or not request.user.has_perm('customer_telegram.publish_customertelegramcampaign')
        ):
            raise PermissionDenied
        info = self.model._meta.app_label, self.model._meta.model_name
        change_url = reverse(
            '{}:{}_{}_change'.format(self.admin_site.name, *info),
            args=(campaign.pk,),
        )
        if campaign.status != CustomerTelegramCampaign.DRAFT:
            self.message_user(
                request,
                'Запустить можно только кампанию со статусом «Черновик».',
                level=messages.WARNING,
            )
            return HttpResponseRedirect(change_url)
        if request.method == 'POST' and request.POST.get('confirm_publish') == 'yes':
            self._publish_campaign(campaign)
            self.message_user(request, 'Кампания поставлена в очередь на отправку.')
            return HttpResponseRedirect(change_url)
        return TemplateResponse(
            request,
            'admin/customer_telegram/customertelegramcampaign/publish_confirmation.html',
            {
                **self.admin_site.each_context(request),
                'title': 'Подтвердите запуск рассылки',
                'campaign': campaign,
                'opts': self.model._meta,
                'change_url': change_url,
            },
        )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status != CustomerTelegramCampaign.DRAFT:
            fields.extend((
                'name', 'status', 'scheduled_at', 'test_recipient', 'title_ru', 'title_uz',
                'body_ru', 'body_uz', 'button_text_ru', 'button_text_uz', 'button_url',
            ))
        return tuple(dict.fromkeys(fields))

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _retry_count=Count('recipients', filter=Q(recipients__status='retry')),
        )

    @admin.display(description='Повторные попытки', ordering='_retry_count')
    def retry_count(self, obj):
        return obj._retry_count

    @admin.display(description='Предпросмотр RU')
    def preview_ru(self, obj):
        return _preview(obj.title_ru, obj.body_ru, obj.button_text_ru, obj.button_url)

    @admin.display(description='Предпросмотр UZ')
    def preview_uz(self, obj):
        return _preview(obj.title_uz, obj.body_uz, obj.button_text_uz, obj.button_url)

    @admin.action(description='Поставить выбранные кампании в очередь')
    def publish_campaigns(self, request, queryset):
        if not request.user.has_perm('customer_telegram.publish_customertelegramcampaign'):
            self.message_user(request, 'Недостаточно прав.', level=messages.ERROR)
            return
        if request.POST.get('confirm_publish') != 'yes':
            return TemplateResponse(
                request,
                'admin/customer_telegram/campaign_publish_confirmation.html',
                {
                    **self.admin_site.each_context(request),
                    'title': 'Подтвердите отправку кампаний',
                    'queryset': queryset.filter(status=CustomerTelegramCampaign.DRAFT),
                    'opts': self.model._meta,
                    'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
                    'action_name': 'publish_campaigns',
                },
            )
        published = 0
        for campaign in queryset:
            if campaign.status != CustomerTelegramCampaign.DRAFT:
                continue
            self._publish_campaign(campaign)
            published += 1
        self.message_user(request, 'Кампаний поставлено в очередь: {}'.format(published))

    @staticmethod
    def _publish_campaign(campaign):
        campaign.full_clean()
        campaign.status = (
            CustomerTelegramCampaign.SCHEDULED
            if campaign.scheduled_at and campaign.scheduled_at > timezone.now()
            else CustomerTelegramCampaign.QUEUEING
        )
        campaign.save(update_fields=('status', 'updated_at'))

    @admin.action(description='Отправить тест выбранных кампаний')
    def test_campaigns(self, request, queryset):
        if not request.user.has_perm('customer_telegram.test_customertelegramcampaign'):
            self.message_user(request, 'Недостаточно прав.', level=messages.ERROR)
            return
        delivered = 0
        for campaign in queryset.filter(status=CustomerTelegramCampaign.DRAFT).select_related('test_recipient'):
            if campaign.test_recipient and send_test_campaign(campaign, campaign.test_recipient):
                delivered += 1
        self.message_user(request, 'Тестовых сообщений доставлено: {}'.format(delivered))

    @admin.action(description='Отменить выбранные кампании')
    def cancel_campaigns(self, request, queryset):
        updated = queryset.filter(status__in=(
            CustomerTelegramCampaign.DRAFT,
            CustomerTelegramCampaign.SCHEDULED,
            CustomerTelegramCampaign.QUEUEING,
        )).update(status=CustomerTelegramCampaign.CANCELLED)
        self.message_user(request, 'Кампаний отменено: {}'.format(updated))

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (
            obj is None or obj.status == CustomerTelegramCampaign.DRAFT
        )


@admin.register(CustomerTelegramCampaignRecipient, site=bodysteel_admin_site)
class CustomerTelegramCampaignRecipientAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'chat', 'language', 'status', 'attempt_count', 'delivered_at')
    list_filter = ('status', 'language', 'created_at')
    list_select_related = ('campaign', 'chat')
    readonly_fields = [field.name for field in CustomerTelegramCampaignRecipient._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _preview(title, body, button_text, button_url):
    button = format_html('<p><strong>{}</strong><br>{}</p>', button_text, button_url) if button_text else ''
    return format_html(
        '<div style="max-width:620px;padding:16px;border:1px solid #dfe5df;border-radius:10px">'
        '<strong>{}</strong><p style="white-space:pre-wrap">{}</p>{}</div>',
        title, body, button,
    )
