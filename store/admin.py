from django.contrib import admin
from store.models import Menu, Filial, Product, SetOfProduct, Category, Blog, Brand, ProductImage, Review, Order


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    fields = ['name_', 'about_uz', 'blog_uz', 'set_product_uz', 'delivery_and_payment_uz', 'about_ru', 'blog_ru',
              'set_product_ru', 'delivery_and_payment_ru', 'is_active', ]
    list_display = ['name', 'is_active']


@admin.register(Filial)
class FilialAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'address_uz', 'address_ru', 'phone']


@admin.register(SetOfProduct)
class SetOfProductAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'photo']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'photo', 'sort']


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'photo']


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name', 'photo']


@admin.register(Product)
class ProductsAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'name_uz', 'name_ru', 'price', 'quantity', 'view_count']


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'product', 'photo']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'full_name', 'rating', 'product', 'created_at']


@admin.register(Order)
class OrdersAdmin(admin.ModelAdmin):
    empty_value_display = "-пусто-"
    list_display = ['id', 'full_name', 'phone', 'type', 'total_price', 'status']
