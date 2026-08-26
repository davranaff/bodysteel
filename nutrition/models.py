from django.core.exceptions import ValidationError
from django.db import models

from store.fields import SanitizedHtmlField
from store.catalog.models import Product


class DeliveryMethod(models.Model):
    COURIER = 'courier'
    PICKUP = 'pickup'
    KIND_CHOICES = ((COURIER, 'Курьер'), (PICKUP, 'Самовывоз'))

    code = models.SlugField(max_length=50, unique=True, verbose_name='Код способа доставки')
    name_ru = models.CharField(max_length=100, verbose_name='Название на русском')
    name_uz = models.CharField(max_length=100, verbose_name='Название на узбекском')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=COURIER, verbose_name='Тип доставки')
    base_fee = models.PositiveBigIntegerField(default=0, verbose_name='Базовая стоимость доставки')
    minimum_order = models.PositiveBigIntegerField(default=0, verbose_name='Минимальная сумма заказа')
    free_from = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name='Бесплатная доставка от суммы',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Способ доставки'
        verbose_name_plural = 'Способы доставки'

    def __str__(self):
        return self.name_ru


class DeliveryZone(models.Model):
    code = models.SlugField(max_length=100, unique=True, verbose_name='Код зоны')
    name_ru = models.CharField(max_length=150, verbose_name='Название на русском')
    name_uz = models.CharField(max_length=150, verbose_name='Название на узбекском')
    fee = models.PositiveBigIntegerField(default=0, verbose_name='Стоимость доставки')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        verbose_name = 'Зона доставки'
        verbose_name_plural = 'Зоны доставки'

    def __str__(self):
        return self.name_ru


class DeliverySlot(models.Model):
    zone = models.ForeignKey(
        DeliveryZone,
        on_delete=models.CASCADE,
        related_name='slots',
        verbose_name='Зона доставки',
    )
    delivery_date = models.DateField(verbose_name='Дата доставки')
    starts_at = models.TimeField(verbose_name='Время начала интервала')
    ends_at = models.TimeField(verbose_name='Время окончания интервала')
    cutoff_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Принимать заказы до',
    )
    capacity = models.PositiveIntegerField(default=0, verbose_name='Вместимость интервала')
    reserved_count = models.PositiveIntegerField(default=0, verbose_name='Зарезервировано мест')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        ordering = ('delivery_date', 'starts_at')
        constraints = [
            models.UniqueConstraint(
                fields=('zone', 'delivery_date', 'starts_at', 'ends_at'),
                name='delivery_slot_identity',
            ),
        ]
        verbose_name = 'Интервал доставки'
        verbose_name_plural = 'Интервалы доставки'

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
    slug = models.SlugField(max_length=80, unique=True, verbose_name='Адрес тега (URL)')
    name_ru = models.CharField(max_length=100, verbose_name='Название на русском')
    name_uz = models.CharField(max_length=100, verbose_name='Название на узбекском')

    class Meta:
        verbose_name = 'Тег блюда'
        verbose_name_plural = 'Теги блюд'

    def __str__(self):
        return self.name_ru


class Allergen(models.Model):
    slug = models.SlugField(max_length=80, unique=True, verbose_name='Адрес аллергена (URL)')
    name_ru = models.CharField(max_length=100, verbose_name='Название на русском')
    name_uz = models.CharField(max_length=100, verbose_name='Название на узбекском')

    class Meta:
        verbose_name = 'Аллерген'
        verbose_name_plural = 'Аллергены'

    def __str__(self):
        return self.name_ru


class NutritionProfile(models.Model):
    DISH = 'dish'
    KIT = 'meal_kit'
    KIND_CHOICES = ((DISH, 'Блюдо'), (KIT, 'Набор'))

    product = models.OneToOneField(
        'store.Product',
        on_delete=models.CASCADE,
        related_name='nutrition_profile',
        verbose_name='Товар',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=DISH, verbose_name='Тип питания')
    portion_weight_grams = models.PositiveIntegerField(default=0, verbose_name='Вес порции, г')
    servings = models.PositiveIntegerField(default=1, verbose_name='Количество порций')
    calories_kcal = models.PositiveIntegerField(default=0, verbose_name='Калорийность, ккал')
    protein_grams = models.DecimalField(max_digits=7, decimal_places=2, default=0, verbose_name='Белки, г')
    fat_grams = models.DecimalField(max_digits=7, decimal_places=2, default=0, verbose_name='Жиры, г')
    carbohydrate_grams = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        verbose_name='Углеводы, г',
    )
    shelf_life_hours = models.PositiveIntegerField(default=0, verbose_name='Срок хранения, часов')
    storage_ru = SanitizedHtmlField(blank=True, default='', verbose_name='Условия хранения на русском')
    storage_uz = SanitizedHtmlField(blank=True, default='', verbose_name='Условия хранения на узбекском')
    serving_ru = SanitizedHtmlField(blank=True, default='', verbose_name='Рекомендации по подаче на русском')
    serving_uz = SanitizedHtmlField(blank=True, default='', verbose_name='Рекомендации по подаче на узбекском')
    requires_cooling = models.BooleanField(default=False, verbose_name='Требует охлаждения')
    is_available = models.BooleanField(default=True, verbose_name='Доступен для заказа')
    tags = models.ManyToManyField(
        FoodTag,
        blank=True,
        related_name='nutrition_profiles',
        verbose_name='Теги блюда',
    )
    allergens = models.ManyToManyField(
        Allergen,
        blank=True,
        related_name='nutrition_profiles',
        verbose_name='Аллергены',
    )
    allowed_delivery_methods = models.ManyToManyField(
        DeliveryMethod,
        blank=True,
        related_name='nutrition_profiles',
        verbose_name='Разрешённые способы доставки',
    )

    class Meta:
        verbose_name = 'Профиль питания'
        verbose_name_plural = 'Профили питания'

    def clean(self):
        expected = {'meal': self.DISH, 'meal_kit': self.KIT}
        if self.product_id and self.product.product_type in expected and expected[self.product.product_type] != self.kind:
            raise ValidationError({'kind': 'Тип профиля не совпадает с типом продукта'})

    def __str__(self):
        return self.product.name_ru


class MealKitItem(models.Model):
    kit = models.ForeignKey(
        'store.Product',
        on_delete=models.CASCADE,
        related_name='kit_items',
        verbose_name='Набор',
    )
    component = models.ForeignKey(
        'store.Product',
        on_delete=models.PROTECT,
        related_name='included_in_kits',
        verbose_name='Блюдо в наборе',
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    position = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')

    class Meta:
        ordering = ('position', 'id')
        constraints = [
            models.UniqueConstraint(fields=('kit', 'component'), name='meal_kit_component_unique'),
        ]
        verbose_name = 'Блюдо в наборе'
        verbose_name_plural = 'Блюда в наборе'

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
