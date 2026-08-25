from django.contrib import admin

from nutrition.models import Allergen, DeliveryMethod, DeliverySlot, DeliveryZone, FoodTag, MealKitItem, MealProduct, NutritionProfile
from store.admin_catalog import ProductAdmin
from store.admin_site import bodysteel_admin_site


class NutritionProfileInline(admin.StackedInline):
    model = NutritionProfile
    extra = 0
    max_num = 1
    fields = (
        ('kind', 'portion_weight_grams', 'servings'),
        ('calories_kcal', 'protein_grams', 'fat_grams', 'carbohydrate_grams'),
        ('shelf_life_hours', 'requires_cooling', 'is_available'),
        ('storage_ru', 'storage_uz'), ('serving_ru', 'serving_uz'),
        'tags', 'allergens', 'allowed_delivery_methods',
    )
    autocomplete_fields = ('tags', 'allergens', 'allowed_delivery_methods')


class MealKitItemInline(admin.TabularInline):
    model = MealKitItem
    fk_name = 'kit'
    extra = 0
    autocomplete_fields = ('component',)
    fields = ('component', 'quantity', 'position')


@admin.register(MealProduct, site=bodysteel_admin_site)
class MealProductAdmin(ProductAdmin):
    list_display = ('product_name', 'meal_kind', 'price_display', 'stock_badge', 'is_new', 'updated_at')
    list_filter = ('product_type', 'brand', 'category', 'nutrition_profile__kind', 'nutrition_profile__is_available')
    inlines = (ProductAdmin.inlines[0], ProductAdmin.inlines[1], NutritionProfileInline, MealKitItemInline)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(product_type__in=('meal', 'meal_kit'))

    def save_model(self, request, obj, form, change):
        if obj.product_type not in ('meal', 'meal_kit'):
            obj.product_type = 'meal'
        super().save_model(request, obj, form, change)

    @admin.display(description='Тип')
    def meal_kind(self, obj):
        return obj.get_product_type_display()


@admin.register(NutritionProfile, site=bodysteel_admin_site)
class NutritionProfileAdmin(admin.ModelAdmin):
    list_display = ('product', 'kind', 'calories_kcal', 'protein_grams', 'is_available')
    list_filter = ('kind', 'is_available', 'requires_cooling')
    search_fields = ('product__name_ru', 'product__name_uz')
    autocomplete_fields = ('product', 'tags', 'allergens', 'allowed_delivery_methods')


@admin.register(FoodTag, site=bodysteel_admin_site)
class FoodTagAdmin(admin.ModelAdmin):
    list_display = ('name_ru', 'name_uz', 'slug')
    search_fields = ('name_ru', 'name_uz', 'slug')


@admin.register(Allergen, site=bodysteel_admin_site)
class AllergenAdmin(FoodTagAdmin):
    pass


@admin.register(DeliveryMethod, site=bodysteel_admin_site)
class DeliveryMethodAdmin(admin.ModelAdmin):
    list_display = ('name_ru', 'code', 'kind', 'base_fee', 'minimum_order', 'is_active')
    list_filter = ('kind', 'is_active')
    search_fields = ('name_ru', 'name_uz', 'code')


@admin.register(DeliveryZone, site=bodysteel_admin_site)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ('name_ru', 'code', 'fee', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name_ru', 'name_uz', 'code')


@admin.register(DeliverySlot, site=bodysteel_admin_site)
class DeliverySlotAdmin(admin.ModelAdmin):
    list_display = ('zone', 'delivery_date', 'starts_at', 'ends_at', 'capacity', 'reserved_count', 'is_active')
    list_filter = ('zone', 'delivery_date', 'is_active')
    date_hierarchy = 'delivery_date'
    autocomplete_fields = ('zone',)
