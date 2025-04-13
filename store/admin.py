from django.contrib import admin
from store.models import Basket, Menu, Filial, Product, SetOfProduct, Category, Blog, Brand, ProductImage, Review, Order, Coupon


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    fields = ['name', 'about_uz', 'blog_uz', 'set_product_uz', 'delivery_and_payment_uz', 'about_ru', 'blog_ru',
              'set_product_ru', 'delivery_and_payment_ru', 'is_active', 'delivery_price', 'bank_card_number',
              'uzbekistan_description_uz', 'bukhara_description_uz', 'uzbekistan_description_ru', 'bukhara_description_ru', 'bonus']
    list_display = ['name', 'is_active']


@admin.register(Filial)
class FilialAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'address_uz', 'address_ru', 'phone']


@admin.register(SetOfProduct)
class SetOfProductAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'photo', 'slug']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'photo', 'sort', 'slug']


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'photo', 'slug']


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name', 'photo']


class ProductImageInline(admin.TabularInline):
    model = ProductImage


@admin.register(Product)
class ProductsAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'price', 'quantity', 'view_count']
    exclude = ['view_count']
    inlines = [ProductImageInline]
    list_filter = ['name_ru']
    list_editable = ('name_uz', 'name_ru', 'quantity')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'product', 'photo']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'full_name', 'rating', 'product', 'created_at']
    list_filter = ['rating']


@admin.register(Order)
class OrdersAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'full_name', 'phone', 'type', 'total_price', 'status', 'created_at']
    list_editable = ['status', ]
    readonly_fields = ['full_name', 'phone', 'type', 'total_price', 'order_code', 'address', 'fix_check']


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'code', 'discount_percent', 'max_uses', 'used_count', 'is_active', 'created_at']
    list_editable = ['is_active', 'discount_percent']
    list_filter = ['is_active', 'discount_percent']
    search_fields = ['code']
