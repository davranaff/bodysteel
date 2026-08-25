from django.contrib import admin

from payments.models import Payment, PaymentEvent
from store.admin_site import bodysteel_admin_site, format_uzs


@admin.register(Payment, site=bodysteel_admin_site)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'target', 'provider', 'amount_display', 'status', 'created_at', 'paid_at')
    list_filter = ('provider', 'status', 'currency', 'created_at')
    search_fields = ('provider_payment_id', 'order__order_code', 'course_purchase__course_title', 'course_purchase__user__phone')
    readonly_fields = ('order', 'course_purchase', 'provider', 'provider_payment_id', 'amount', 'currency', 'idempotency_digest', 'metadata', 'created_at', 'updated_at', 'paid_at')

    @admin.display(description='Объект')
    def target(self, obj):
        return obj.order or obj.course_purchase

    @admin.display(description='Сумма')
    def amount_display(self, obj):
        return format_uzs(obj.amount)


@admin.register(PaymentEvent, site=bodysteel_admin_site)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ('provider', 'external_event_id', 'event_type', 'processing_status', 'created_at')
    list_filter = ('provider', 'event_type', 'processing_status', 'created_at')
    search_fields = ('external_event_id', 'payload_hash')
    readonly_fields = ('payment', 'provider', 'external_event_id', 'event_type', 'payload_hash', 'created_at')
