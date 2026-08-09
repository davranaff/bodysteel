from django.contrib import admin
from django.utils.html import format_html

from store.admin_shared import Product360ImageInline, ProductImageInline, ProductStateFilter, StockFilter
from store.admin_site import admin_url, bodysteel_admin_site, format_uzs
from store.models import FilialPhoto, Product, Product360Image, ProductImage, Review


@admin.register(Product, site=bodysteel_admin_site)
class ProductAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    save_on_top = True
    save_as = True
    list_display = ('product_name', 'brand_name', 'price_display', 'stock_badge', 'regos_badge', 'is_new', 'updated_at')
    list_filter = (StockFilter, ProductStateFilter, 'brand', 'category')
    search_fields = ('name_ru', 'name_uz', 'slug', 'regos_item_code', 'regos_item_articul')
    date_hierarchy = 'updated_at'
    ordering = ('-updated_at',)
    list_select_related = ('brand',)
    list_per_page = 25
    autocomplete_fields = ('brand', 'category', 'set_of_products')
    prepopulated_fields = {'slug': ('name_ru',)}
    readonly_fields = ('view_count', 'updated_at', 'regos_item_id', 'regos_item_code', 'regos_item_articul')
    inlines = (ProductImageInline, Product360ImageInline)
    actions = ('mark_new',)
    fieldsets = (
        ('Основное', {
            'fields': (('name_ru', 'name_uz'), ('brand', 'category'), 'set_of_products', ('slug', 'is_new')),
        }),
        ('Цена и остаток', {'fields': (('price', 'discounted_price'), 'quantity')}),
        ('Описание и состав', {
            'fields': (
                ('country_ru', 'country_uz'),
                ('description_ru', 'description_uz'),
                ('composition_ru', 'composition_uz'),
            ),
        }),
        ('Интеграции и аналитика', {
            'classes': ('collapse',),
            'fields': (('regos_item_id', 'regos_item_code'), 'regos_item_articul', ('view_count', 'updated_at')),
        }),
    )

    @admin.display(description='Товар', ordering='name_ru')
    def product_name(self, obj):
        return format_html('<a class="bs-object-link" href="{}">{}</a>', admin_url(Product, 'change', obj.pk), obj.name_ru)

    @admin.display(description='Бренд', ordering='brand__name')
    def brand_name(self, obj):
        return obj.brand.name if obj.brand else 'Без бренда'

    @admin.display(description='Цена', ordering='price')
    def price_display(self, obj):
        current = obj.price - obj.discounted_price
        if obj.discounted_price:
            return format_html('<strong>{}</strong><br><del>{}</del>', format_uzs(current), format_uzs(obj.price))
        return format_html('<strong>{}</strong>', format_uzs(current))

    @admin.display(description='Остаток', ordering='quantity')
    def stock_badge(self, obj):
        if obj.quantity == 0:
            tone, label = 'danger', 'Нет в наличии'
        elif obj.quantity <= 5:
            tone, label = 'warning', '{} шт.'.format(obj.quantity)
        else:
            tone, label = 'success', '{} шт.'.format(obj.quantity)
        return format_html('<span class="bs-status bs-status--{}">{}</span>', tone, label)

    @admin.display(description='REGOS')
    def regos_badge(self, obj):
        label = 'Синхронизирован' if obj.regos_item_id else 'Не привязан'
        tone = 'success' if obj.regos_item_id else 'muted'
        return format_html('<span class="bs-status bs-status--{}">{}</span>', tone, label)

    @admin.action(description='Пометить как новинки')
    def mark_new(self, request, queryset):
        updated = queryset.update(is_new=True)
        self.message_user(request, 'Обновлено карточек: {}'.format(updated))


@admin.register(ProductImage, site=bodysteel_admin_site)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'preview', 'photo')
    search_fields = ('product__name_ru', 'product__name_uz')
    list_select_related = ('product',)

    @admin.display(description='Превью')
    def preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-inline-image" src="{}" alt="">', obj.photo.url)


@admin.register(FilialPhoto, site=bodysteel_admin_site)
class FilialPhotoAdmin(admin.ModelAdmin):
    list_display = ('filial', 'preview', 'created_at')
    list_filter = ('filial',)
    search_fields = ('filial__name_ru', 'filial__name_uz')
    list_select_related = ('filial',)

    @admin.display(description='Превью')
    def preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-inline-image" src="{}" alt="">', obj.photo.url)


@admin.register(Product360Image, site=bodysteel_admin_site)
class Product360ImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'preview', 'sort_order')
    list_filter = ('product',)
    search_fields = ('product__name_ru', 'product__name_uz')
    list_editable = ('sort_order',)
    ordering = ('product', 'sort_order')
    list_select_related = ('product',)

    @admin.display(description='Кадр')
    def preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-inline-image bs-inline-image--small" src="{}" alt="">', obj.photo.url)


@admin.register(Review, site=bodysteel_admin_site)
class ReviewAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    list_display = ('rating_badge', 'full_name', 'product', 'comment_preview', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('full_name', 'comment', 'product__name_ru')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    list_select_related = ('product', 'user')

    @admin.display(description='Оценка', ordering='rating')
    def rating_badge(self, obj):
        return format_html('<span class="bs-rating">{} <small>/ 5</small></span>', obj.rating)

    @admin.display(description='Комментарий')
    def comment_preview(self, obj):
        return (obj.comment or 'Без комментария')[:72]
