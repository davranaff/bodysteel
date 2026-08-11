from django.contrib import admin
from django.utils.html import format_html

from store.models import Basket, FilialPhoto, Product360Image, ProductImage


class StockFilter(admin.SimpleListFilter):
    title = 'остаток'
    parameter_name = 'stock'

    def lookups(self, request, model_admin):
        return (
            ('available', 'В наличии'),
            ('low', 'Заканчивается'),
            ('empty', 'Нет на складе'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'available':
            return queryset.filter(quantity__gt=5)
        if self.value() == 'low':
            return queryset.filter(quantity__gt=0, quantity__lte=5)
        if self.value() == 'empty':
            return queryset.filter(quantity=0)
        return queryset


class ProductStateFilter(admin.SimpleListFilter):
    title = 'состояние карточки'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return (
            ('sale', 'Со скидкой'),
            ('new', 'Новинки'),
            ('regos', 'Связаны с REGOS'),
            ('unlinked', 'Без связи с REGOS'),
            ('regos_drafts', 'Черновики REGOS'),
            ('regos_archived', 'Архив REGOS'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'sale':
            return queryset.filter(discounted_price__gt=0)
        if self.value() == 'new':
            return queryset.filter(is_new=True)
        if self.value() == 'regos':
            return queryset.filter(regos_item_id__isnull=False)
        if self.value() == 'unlinked':
            return queryset.filter(regos_item_id__isnull=True)
        if self.value() == 'regos_drafts':
            return queryset.filter(regos_catalog_status='draft')
        if self.value() == 'regos_archived':
            return queryset.filter(regos_catalog_status='archived')
        return queryset


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ('preview', 'photo')
    readonly_fields = ('preview',)
    classes = ('collapse',)

    @admin.display(description='Превью')
    def preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-inline-image" src="{}" alt="">', obj.photo.url)


class Product360ImageInline(admin.TabularInline):
    model = Product360Image
    extra = 0
    fields = ('preview', 'photo', 'sort_order')
    readonly_fields = ('preview',)
    ordering = ('sort_order',)
    classes = ('collapse',)

    @admin.display(description='Кадр')
    def preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-inline-image bs-inline-image--small" src="{}" alt="">', obj.photo.url)


class FilialPhotoInline(admin.TabularInline):
    model = FilialPhoto
    extra = 0
    fields = ('preview', 'photo', 'created_at')
    readonly_fields = ('preview', 'created_at')

    @admin.display(description='Превью')
    def preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-inline-image" src="{}" alt="">', obj.photo.url)


class BasketInline(admin.TabularInline):
    model = Basket
    extra = 0
    fields = ('product', 'quantity', 'price', 'user', 'created_at')
    readonly_fields = fields
    can_delete = False
    show_change_link = True
