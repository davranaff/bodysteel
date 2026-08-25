from django.core.exceptions import ValidationError
from django.db import models

from store.fields import SanitizedHtmlField
from store.catalog.models import Product


class DeliveryMethod(models.Model):
    COURIER = 'courier'
    PICKUP = 'pickup'
    KIND_CHOICES = ((COURIER, 'Курьер'), (PICKUP, 'Самовывоз'))

    code = models.SlugField(max_length=50, unique=True)
    name_ru = models.CharField(max_length=100)
    name_uz = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=COURIER)
    base_fee = models.PositiveBigIntegerField(default=0)
    minimum_order = models.PositiveBigIntegerField(default=0)
    free_from = models.PositiveBigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name_ru


class DeliveryZone(models.Model):
    code = models.SlugField(max_length=100, unique=True)
    name_ru = models.CharField(max_length=150)
    name_uz = models.CharField(max_length=150)
    fee = models.PositiveBigIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name_ru


class DeliverySlot(models.Model):
    zone = models.ForeignKey(DeliveryZone, on_delete=models.CASCADE, related_name='slots')
    delivery_date = models.DateField()
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    cutoff_at = models.DateTimeField(null=True, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    reserved_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('delivery_date', 'starts_at')
        constraints = [
            models.UniqueConstraint(
                fields=('zone', 'delivery_date', 'starts_at', 'ends_at'),
                name='delivery_slot_identity',
            ),
        ]

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'Время окончания должно быть позже начала'})
        if self.reserved_count > self.capacity:
            raise ValidationError({'reserved_count': 'Занятых мест больше вместимости'})

    def has_capacity(self):
        return self.is_active and self.reserved_count < self.capacity

    def __str__(self):
        return '{} {}-{}'.format(self.delivery_date, self.starts_at, self.ends_at)


class FoodTag(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    name_ru = models.CharField(max_length=100)
    name_uz = models.CharField(max_length=100)

    def __str__(self):
        return self.name_ru


class Allergen(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    name_ru = models.CharField(max_length=100)
    name_uz = models.CharField(max_length=100)

    def __str__(self):
        return self.name_ru


class NutritionProfile(models.Model):
    DISH = 'dish'
    KIT = 'meal_kit'
    KIND_CHOICES = ((DISH, 'Блюдо'), (KIT, 'Набор'))

    product = models.OneToOneField('store.Product', on_delete=models.CASCADE, related_name='nutrition_profile')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=DISH)
    portion_weight_grams = models.PositiveIntegerField(default=0)
    servings = models.PositiveIntegerField(default=1)
    calories_kcal = models.PositiveIntegerField(default=0)
    protein_grams = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    fat_grams = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    carbohydrate_grams = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    shelf_life_hours = models.PositiveIntegerField(default=0)
    storage_ru = SanitizedHtmlField(blank=True, default='')
    storage_uz = SanitizedHtmlField(blank=True, default='')
    serving_ru = SanitizedHtmlField(blank=True, default='')
    serving_uz = SanitizedHtmlField(blank=True, default='')
    requires_cooling = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    tags = models.ManyToManyField(FoodTag, blank=True, related_name='nutrition_profiles')
    allergens = models.ManyToManyField(Allergen, blank=True, related_name='nutrition_profiles')
    allowed_delivery_methods = models.ManyToManyField(DeliveryMethod, blank=True, related_name='nutrition_profiles')

    def clean(self):
        expected = {'meal': self.DISH, 'meal_kit': self.KIT}
        if self.product_id and self.product.product_type in expected and expected[self.product.product_type] != self.kind:
            raise ValidationError({'kind': 'Тип профиля не совпадает с типом продукта'})

    def __str__(self):
        return self.product.name_ru


class MealKitItem(models.Model):
    kit = models.ForeignKey('store.Product', on_delete=models.CASCADE, related_name='kit_items')
    component = models.ForeignKey('store.Product', on_delete=models.PROTECT, related_name='included_in_kits')
    quantity = models.PositiveIntegerField(default=1)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('position', 'id')
        constraints = [
            models.UniqueConstraint(fields=('kit', 'component'), name='meal_kit_component_unique'),
        ]

    def clean(self):
        if self.kit_id and self.component_id and self.kit_id == self.component_id:
            raise ValidationError('Набор не может содержать сам себя')

    def __str__(self):
        return '{} x {}'.format(self.kit.name_ru, self.component.name_ru)


class MealProduct(Product):
    class Meta:
        managed = False
        proxy = True
        verbose_name = 'Блюдо правильного питания'
        verbose_name_plural = 'Правильное питание'
