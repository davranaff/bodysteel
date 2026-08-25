from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from store.fields import SanitizedHtmlField
from store.models import (
    BaseModel,
    category_directory_path,
    product_360_directory_path,
    product_image_directory_path,
)
from store.querysets.product import ProductQueryset
from users.models import User


class Category(BaseModel):
    name_uz = models.CharField(max_length=255, verbose_name='Название категории uz')
    name_ru = models.CharField(max_length=255, verbose_name='Название категории ru')
    photo = models.ImageField(
        upload_to=category_directory_path,
        verbose_name='Картинка категории',
    )
    slug = models.SlugField(
        verbose_name='без пробела, либо через "-", либо через "_"',
        null=True,
        blank=True,
    )
    description = SanitizedHtmlField(verbose_name='Описание категории')
    sort = models.PositiveIntegerField(
        verbose_name='Сортировка Категории',
        help_text='сортируется по возрастанию, у каждой категории должен быть уникальный номер',
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name_ru

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        unique_together = ('name_uz', 'name_ru', 'sort')


class Product(BaseModel):
    TYPE_SUPPLEMENT = 'supplement'
    TYPE_MEAL = 'meal'
    TYPE_MEAL_KIT = 'meal_kit'
    PRODUCT_TYPE_CHOICES = (
        (TYPE_SUPPLEMENT, 'Спортивное питание'),
        (TYPE_MEAL, 'Готовое блюдо'),
        (TYPE_MEAL_KIT, 'Набор правильного питания'),
    )

    REGOS_STATUS_MANUAL = 'manual'
    REGOS_STATUS_DRAFT = 'draft'
    REGOS_STATUS_PUBLISHED = 'published'
    REGOS_STATUS_ARCHIVED = 'archived'
    REGOS_CATALOG_STATUS_CHOICES = (
        (REGOS_STATUS_MANUAL, 'Обычная карточка'),
        (REGOS_STATUS_DRAFT, 'Черновик из REGOS'),
        (REGOS_STATUS_PUBLISHED, 'Опубликован из REGOS'),
        (REGOS_STATUS_ARCHIVED, 'Архивирован из REGOS'),
    )

    updated_at = models.DateTimeField(auto_now=True)
    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_TYPE_CHOICES,
        default=TYPE_SUPPLEMENT,
        db_index=True,
        verbose_name='Тип физического товара',
    )
    regos_item_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name='REGOS ID номенклатуры',
        help_text='Заполняется автоматически при синхронизации с REGOS.',
    )
    regos_item_code = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='Код номенклатуры REGOS',
        help_text='Заполняется автоматически при синхронизации с REGOS.',
    )
    regos_item_articul = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name='Артикул REGOS',
        help_text='Заполняется автоматически при синхронизации с REGOS.',
    )
    regos_catalog_status = models.CharField(
        max_length=16,
        choices=REGOS_CATALOG_STATUS_CHOICES,
        default=REGOS_STATUS_MANUAL,
        db_index=True,
        verbose_name='Статус карточки REGOS',
        help_text='Черновики и архивированные позиции не показываются на витрине и недоступны для заказа.',
    )
    name_uz = models.CharField(max_length=500, verbose_name='Название Продукта uz', unique=True)
    name_ru = models.CharField(max_length=500, verbose_name='Название Продукта ru', unique=True)
    description_uz = SanitizedHtmlField(verbose_name='Описание Товара uz', null=True, blank=True)
    description_ru = SanitizedHtmlField(verbose_name='Описание Товара ru', null=True, blank=True)
    price = models.PositiveBigIntegerField(verbose_name='Стоимость товара')
    is_new = models.BooleanField(
        default=True,
        verbose_name='Новый товар',
        help_text='Если вкл. то на сайте будет показывать, что этот товар "Новинка"',
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name='Кол-во. Товара на складе')
    discounted_price = models.PositiveBigIntegerField(
        default=0,
        verbose_name='Скидочная цена',
        help_text=(
            'Если есть скидка на товар, то вы '
            'должны здесь написать на какую сумму '
            'скидка (пример: сам товар стоит 120000 сум, '
            'скидка на 20000 сум. итог:100000'
            'здесь 20000 сум скидочная цена)'
        ),
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name='Название товара (url)',
        editable=True,
        help_text='без пробела, либо через "-", либо через "_"',
    )
    country_uz = models.CharField(max_length=100, verbose_name='Старана-Производитель uz')
    country_ru = models.CharField(max_length=100, verbose_name='Старана-Производитель ru')
    composition_uz = SanitizedHtmlField(verbose_name='Состав продукта uz', null=True, blank=True)
    composition_ru = SanitizedHtmlField(verbose_name='Состав продукта ru', null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0, verbose_name='Кол-во. просмотров')
    category = models.ManyToManyField(
        'Category',
        verbose_name='Категория продукта',
        related_name='products',
        related_query_name='products',
        blank=True,
    )
    brand = models.ForeignKey(
        'Brand',
        on_delete=models.SET_NULL,
        verbose_name='Бренд продукта',
        related_name='products',
        related_query_name='products',
        null=True,
        blank=True,
    )
    set_of_products = models.ManyToManyField(
        'SetOfProduct',
        blank=True,
        verbose_name='Выберите Комплект',
        related_name='products',
        related_query_name='products',
    )

    objects = ProductQueryset.as_manager()

    def __str__(self):
        return self.name_ru

    def save(self, *args, **kwargs):
        if self.discounted_price > self.price:
            raise ValueError('скидочная цена не может быть меньше цены продукты!')
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
        indexes = [
            models.Index(fields=['updated_at', 'id'], name='store_prod_updated_id_idx'),
        ]


class ProductImage(models.Model):
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='product_images',
        related_query_name='product_images',
        verbose_name='картинка продуктов',
    )
    photo = models.ImageField(upload_to=product_image_directory_path, verbose_name='Фото продукта')

    def __str__(self):
        return self.product.name_ru

    class Meta:
        verbose_name = 'Картинка продукта'
        verbose_name_plural = 'Картинки продуктов'


class Product360Image(models.Model):
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='product_360_images',
        related_query_name='product_360_images',
        verbose_name='360° изображения продукта',
    )
    photo = models.ImageField(upload_to=product_360_directory_path, verbose_name='Фото для 360°')
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name='Порядок сортировки',
        help_text='Чем меньше число, тем раньше показывается кадр',
    )

    def __str__(self):
        return '360° #{0} - {1}'.format(self.sort_order, self.product.name_ru)

    class Meta:
        verbose_name = '360° Изображение продукта'
        verbose_name_plural = '360° Изображения продуктов'
        ordering = ['sort_order']


class Review(BaseModel):
    full_name = models.CharField(max_length=100, verbose_name='Полное имя')
    rating = models.PositiveIntegerField(
        verbose_name='Рейтинг',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
    )
    comment = models.TextField(verbose_name='Комментария')
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews',
        related_query_name='reviews',
        verbose_name='Какому пользователю принадлежит отзыв',
        null=True,
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='reviews',
        related_query_name='reviews',
        verbose_name='Какому продукту принадлежит отзыв',
    )

    def __str__(self):
        return 'Пользователь: {0}, рейтинг: {1}'.format(self.full_name, self.rating)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']
