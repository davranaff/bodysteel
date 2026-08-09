from django.contrib import admin
from django.utils.html import format_html

from store.admin_shared import FilialPhotoInline
from store.admin_site import bodysteel_admin_site
from store.models import Blog, Brand, Category, Filial, Menu, SetOfProduct


@admin.register(Menu, site=bodysteel_admin_site)
class MenuAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    save_on_top = True
    fieldsets = (
        ('Публичная навигация', {'fields': ('name', 'is_active')}),
        ('Контент на узбекском', {
            'fields': (
                ('about_uz', 'blog_uz'),
                ('set_product_uz', 'delivery_and_payment_uz'),
                ('uzbekistan_description_uz', 'bukhara_description_uz'),
            ),
        }),
        ('Контент на русском', {
            'fields': (
                ('about_ru', 'blog_ru'),
                ('set_product_ru', 'delivery_and_payment_ru'),
                ('uzbekistan_description_ru', 'bukhara_description_ru'),
            ),
        }),
        ('Коммерческие настройки', {'fields': ('delivery_price', 'bonus', 'bank_card_number')}),
    )
    list_display = ('name', 'active_badge', 'delivery_price', 'bonus')
    list_filter = ('is_active',)
    search_fields = ('name',)

    @admin.display(description='Статус', boolean=False)
    def active_badge(self, obj):
        label = 'Активно' if obj.is_active else 'Выключено'
        tone = 'success' if obj.is_active else 'muted'
        return format_html('<span class="bs-status bs-status--{}">{}</span>', tone, label)


@admin.register(Filial, site=bodysteel_admin_site)
class FilialAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    save_on_top = True
    list_display = ('name_ru', 'name_uz', 'phone', 'work_hours', 'address_ru')
    list_filter = ('day_off',)
    search_fields = ('name_ru', 'name_uz', 'address_ru', 'address_uz', 'phone')
    inlines = (FilialPhotoInline,)
    fieldsets = (
        ('Филиал', {'fields': (('name_ru', 'name_uz'), ('phone', 'day_off'))}),
        ('График', {'fields': (('work_time_start', 'work_time_end'),)}),
        ('Адрес', {'fields': (('address_ru', 'address_uz'), 'address_url', 'address_location')}),
        ('Обложка', {'fields': ('photo',)}),
    )

    @admin.display(description='График')
    def work_hours(self, obj):
        return '{} — {}'.format(obj.work_time_start.strftime('%H:%M'), obj.work_time_end.strftime('%H:%M'))


@admin.register(SetOfProduct, site=bodysteel_admin_site)
class SetOfProductAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    save_as = True
    list_display = ('name_ru', 'name_uz', 'slug', 'product_count', 'photo_preview')
    search_fields = ('name_ru', 'name_uz', 'slug')
    readonly_fields = ('photo_preview',)
    prepopulated_fields = {'slug': ('name_ru',)}

    @admin.display(description='Товаров')
    def product_count(self, obj):
        return obj.products.count()

    @admin.display(description='Обложка')
    def photo_preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-cover-image" src="{}" alt="">', obj.photo.url)


@admin.register(Category, site=bodysteel_admin_site)
class CategoryAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    list_display = ('sort', 'name_ru', 'name_uz', 'product_count', 'photo_preview')
    list_display_links = ('name_ru',)
    list_filter = ('sort',)
    search_fields = ('name_ru', 'name_uz', 'slug')
    ordering = ('sort', 'name_ru')
    prepopulated_fields = {'slug': ('name_ru',)}
    readonly_fields = ('photo_preview',)

    @admin.display(description='Товаров')
    def product_count(self, obj):
        return obj.products.count()

    @admin.display(description='Обложка')
    def photo_preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-cover-image" src="{}" alt="">', obj.photo.url)


@admin.register(Blog, site=bodysteel_admin_site)
class BlogAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    save_as = True
    list_display = ('name_ru', 'name_uz', 'slug', 'created_at', 'photo_preview')
    search_fields = ('name_ru', 'name_uz', 'slug', 'description_ru', 'description_uz')
    date_hierarchy = 'created_at'
    prepopulated_fields = {'slug': ('name_ru',)}

    @admin.display(description='Обложка')
    def photo_preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-cover-image" src="{}" alt="">', obj.photo.url)


@admin.register(Brand, site=bodysteel_admin_site)
class BrandAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    list_display = ('name', 'product_count', 'photo_preview')
    search_fields = ('name',)
    readonly_fields = ('photo_preview',)

    @admin.display(description='Товаров')
    def product_count(self, obj):
        return obj.products.count()

    @admin.display(description='Логотип')
    def photo_preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img class="bs-cover-image bs-cover-image--logo" src="{}" alt="">', obj.photo.url)
