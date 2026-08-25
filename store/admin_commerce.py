from django.contrib import admin
from django.utils.html import format_html

from store.admin_shared import BasketInline
from store.admin_site import admin_url, bodysteel_admin_site, format_uzs
from store.models import Basket, Coupon, Order


@admin.register(Order, site=bodysteel_admin_site)
class OrderAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    save_on_top = True
    list_display = ('order_link', 'customer', 'delivery_type', 'total_display', 'status_badge', 'created_at')
    list_filter = ('status', 'type', 'created_at')
    search_fields = ('order_code', 'full_name', 'phone', 'address')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_select_related = ('user', 'coupon')
    list_per_page = 30
    readonly_fields = (
        'order_code', 'full_name', 'phone', 'type', 'total_price', 'subtotal_price', 'discount_price',
        'delivery_fee', 'payment_status', 'fulfillment_status', 'address', 'fix_check',
        'user', 'coupon', 'idempotency_digest', 'request_fingerprint', 'created_at',
    )
    fieldsets = (
        ('Заказ', {'fields': (('order_code', 'status'), ('total_price', 'payment_status', 'fulfillment_status'), ('type', 'subtotal_price', 'discount_price', 'delivery_fee'))}),
        ('Получатель', {'fields': (('full_name', 'phone'), 'address', 'user')}),
        ('Оплата и доставка', {'fields': ('coupon', 'fix_check')}),
        ('Служебные данные', {'classes': ('collapse',), 'fields': ('idempotency_digest', 'request_fingerprint', 'created_at')}),
    )
    inlines = (BasketInline,)
    actions = ('mark_purchased', 'mark_moderation')

    @admin.display(description='Заказ', ordering='order_code')
    def order_link(self, obj):
        return format_html('<a class="bs-object-link bs-order-code" href="{}">#{}</a>', admin_url(Order, 'change', obj.pk), obj.order_code)

    @admin.display(description='Клиент', ordering='full_name')
    def customer(self, obj):
        return format_html('<strong>{}</strong><br><span class="bs-subtle">{}</span>', obj.full_name, obj.phone)

    @admin.display(description='Доставка', ordering='type')
    def delivery_type(self, obj):
        return obj.get_type_display()

    @admin.display(description='Сумма', ordering='total_price')
    def total_display(self, obj):
        return format_html('<strong>{}</strong>', format_uzs(obj.total_price))

    @admin.display(description='Статус', ordering='status')
    def status_badge(self, obj):
        tone = 'success' if obj.status == 'purchased' else 'warning'
        return format_html('<span class="bs-status bs-status--{}">{}</span>', tone, obj.get_status_display())

    @admin.action(description='Перевести выбранные заказы в «Куплен»')
    def mark_purchased(self, request, queryset):
        updated = queryset.update(status='purchased')
        self.message_user(request, 'Заказов отмечено как купленные: {}'.format(updated))

    @admin.action(description='Вернуть выбранные заказы на модерацию')
    def mark_moderation(self, request, queryset):
        updated = queryset.update(status='moderation')
        self.message_user(request, 'Заказов возвращено на модерацию: {}'.format(updated))


@admin.register(Basket, site=bodysteel_admin_site)
class BasketAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'price', 'user', 'order', 'created_at')
    list_filter = ('order', 'created_at')
    search_fields = ('product__name_ru', 'user__phone', 'order__order_code')
    list_select_related = ('product', 'user', 'order')
    readonly_fields = ('price', 'created_at')


@admin.register(Coupon, site=bodysteel_admin_site)
class CouponAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    list_display = ('code', 'discount_percent', 'usage_badge', 'is_active', 'created_at')
    list_editable = ('discount_percent', 'is_active')
    list_filter = ('is_active', 'discount_percent', 'created_at')
    search_fields = ('code',)
    readonly_fields = ('used_count', 'created_at')

    @admin.display(description='Использование')
    def usage_badge(self, obj):
        tone = 'danger' if not obj.can_use() else 'success'
        return format_html('<span class="bs-status bs-status--{}">{} / {}</span>', tone, obj.used_count, obj.max_uses)
