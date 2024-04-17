from ckeditor.fields import RichTextField
from django.db import models

from store.querysets.product import ProductQueryset
from users.models import User
from django.core.validators import MaxValueValidator, MinValueValidator

from users.utils.random_code import random_code


def category_directory_path(instance, filename):
    return 'categories/{0}/{1}'.format(instance.name_ru, filename)


def blog_directory_path(instance, filename):
    return 'blog/{0}/{1}'.format(instance.name_ru, filename)


def brand_directory_path(instance, filename):
    return 'brand/{0}/{1}'.format(instance.name, filename)


def product_image_directory_path(instance, filename):
    return 'product_images/{0}/{1}'.format(instance.product.name_ru, filename)


def check_path(instance, filename):
    return 'checks/{0}/{1}'.format(instance.order_code, filename)


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Menu(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name='Дайте название для этого меню')

    about_uz = RichTextField(verbose_name='О нас', help_text='Текст для раздела о нас uz')
    about_ru = RichTextField(verbose_name='О нас', help_text='Текст для раздела о нас ru')

    blog_uz = RichTextField(verbose_name='Блог', help_text='Текст для раздела Блог uz')
    blog_ru = RichTextField(verbose_name='Блог', help_text='Текст для раздела Блог ru')

    set_product_uz = RichTextField(verbose_name='Комплект', help_text='Текст для раздела Комплект uz')
    set_product_ru = RichTextField(verbose_name='Комплект', help_text='Текст для раздела Комплект ru')

    delivery_and_payment_uz = RichTextField(verbose_name='Доставка и Оплата uz',
                                            help_text='Текст для раздела Доставка и Оплата')
    delivery_and_payment_ru = RichTextField(verbose_name='Доставка и Оплата ru',
                                            help_text='Текст для раздела Доставка и Оплата')

    delivery_price = models.IntegerField(verbose_name='Цена Доставки', default=0)
    bank_card_number = models.CharField(max_length=16, verbose_name='Номер Банковской карты',
                                        help_text='0000 0000 0000 0000')

    is_active = models.BooleanField(default=True, verbose_name='Активировать',
                                    help_text='Если отключено, то не будет видно', unique=True)

    def __str__(self):
        return self.about_ru

    class Meta:
        verbose_name = 'Меню'
        verbose_name_plural = 'Меню'


class Filial(BaseModel):
    name_uz = models.CharField(max_length=100, verbose_name='Название филиала uz')
    name_ru = models.CharField(max_length=100, verbose_name='Название филиала ru')

    address_uz = models.CharField(max_length=255, verbose_name='Адрес филиала (без ссылки) uz',
                                  help_text='Адрес филиала, а не ссылка (Рес. Узбекистан, г. Бухара, ул. Абдулла кодирий 100 дом)')
    address_ru = models.CharField(max_length=255, verbose_name='Адрес филиала (без ссылки) ru',
                                  help_text='Адрес филиала, а не ссылка (Рес. Узбекистан, г. Бухара, ул. Абдулла кодирий 100 дом)')

    work_time_start = models.TimeField(verbose_name='Время старта работы', help_text='от ПН. до СБ.')
    work_time_end = models.TimeField(verbose_name='Время заканчиваие работы', help_text='от ПН. до СБ.')

    day_off = models.CharField(max_length=255, verbose_name='Выходной',
                               help_text='Если вы работаете в выходные дни, то пишите время с какого часа до какого вы работаете, если нет то пишилте Выходной')

    phone = models.CharField(max_length=13, verbose_name='Телефон номер филиала')

    address_url = models.TextField(verbose_name='Адрес филиала (только ссылка)')
    address_location = models.TextField(verbose_name='Локация филиала (только ссылка)', default=None)

    photo = models.ImageField(upload_to='filial/', verbose_name='Фотография филиала')

    def __str__(self):
        return self.name_ru

    class Meta:
        verbose_name = 'Филиал'
        verbose_name_plural = 'Филиалы'


class SetOfProduct(BaseModel):
    name_uz = models.CharField(max_length=255, verbose_name="Название комплекта uz", null=False, blank=False)
    name_ru = models.CharField(max_length=255, verbose_name="Название комплекта ru", null=False, blank=False)

    photo = models.ImageField(upload_to='set/%Y/%m/%d', verbose_name="Картинка комплекта", null=False, blank=False)

    def __str__(self):
        return self.name_ru

    class Meta:
        verbose_name = "Комплект"
        verbose_name_plural = "Комплекты"
        unique_together = ('name_uz', 'name_ru',)


class Category(BaseModel):
    name_uz = models.CharField(max_length=255, verbose_name="Название категории uz", null=False, blank=False)
    name_ru = models.CharField(max_length=255, verbose_name="Название категории ru", null=False, blank=False)

    photo = models.ImageField(upload_to=category_directory_path, verbose_name="Картинка категории", null=False,
                              blank=False)
    sort = models.PositiveIntegerField(verbose_name="Сортировка Категории",
                                       help_text='сортируется по возрастанию, у каждой категории должен быть уникальный номер',
                                       null=True, blank=True)

    def __str__(self):
        return self.name_ru

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        unique_together = ('name_uz', 'name_ru', 'sort')


class Blog(BaseModel):
    name_uz = models.CharField(max_length=255, verbose_name="Название блога uz", unique=True, null=False, blank=False)
    name_ru = models.CharField(max_length=255, verbose_name="Название блога ru", unique=True, null=False, blank=False)

    photo = models.ImageField(upload_to=blog_directory_path, verbose_name="Картинка блога", null=False, blank=False)

    description_uz = RichTextField(verbose_name="Описание блога uz", null=False, blank=False)
    description_ru = RichTextField(verbose_name="Описание блога ru", null=False, blank=False)

    def __str__(self):
        return self.name_ru

    class Meta:
        verbose_name = "Блог"
        verbose_name_plural = "Блоги"


class Brand(BaseModel):
    name = models.CharField(max_length=100, verbose_name="Название бренда", unique=True)
    photo = models.ImageField(upload_to=brand_directory_path, verbose_name="Фотография бренда")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"


class Product(BaseModel):
    name_uz = models.CharField(max_length=100, verbose_name='Название Продукта uz', unique=True)
    name_ru = models.CharField(max_length=100, verbose_name='Название Продукта ru', unique=True)

    description_uz = RichTextField(verbose_name='Описание Товара uz', null=True, blank=True)
    description_ru = RichTextField(verbose_name='Описание Товара ru', null=True, blank=True)

    price = models.PositiveBigIntegerField(verbose_name='Стоимость товара')

    is_new = models.BooleanField(default=True, verbose_name='Новый товар',
                                 help_text='Если вкл. то на сайте будет показывать, что этот товар "Новинка"')

    quantity = models.PositiveIntegerField(default=0, verbose_name='Кол-во. Товара на складе')

    discounted_price = models.PositiveBigIntegerField(default=0, verbose_name='Скидочная цена',
                                                      help_text='Если есть скидка на товар, то вы '
                                                                'должны здесь написать на какую сумму '
                                                                'скидка (пример: сам товар стоит 120000 сум, '
                                                                'скидка на 20000 сум. итог:100000'
                                                                'здесь 20000 сум скидочная цена)')

    slug = models.SlugField(max_length=255, unique=True, verbose_name='Название товара (url)', editable=True,
                            help_text='без пробела, либо через "-", либо через "_"')

    country_uz = models.CharField(max_length=100, verbose_name='Старана-Производитель uz')
    country_ru = models.CharField(max_length=100, verbose_name='Старана-Производитель ru')

    composition_uz = RichTextField(verbose_name='Состав продукта uz', null=True, blank=True)
    composition_ru = RichTextField(verbose_name='Состав продукта ru', null=True, blank=True)

    view_count = models.PositiveIntegerField(default=0, verbose_name='Кол-во. просмотров')

    category = models.ForeignKey('Category', on_delete=models.SET_NULL, verbose_name='Категория продукта',
                                 related_name='products', related_query_name='products', null=True, blank=True)

    brand = models.ForeignKey('Brand', on_delete=models.SET_NULL, verbose_name='Бренд продукта',
                              related_name='products',
                              related_query_name='products', null=True, blank=True)
    set_of_products = models.ForeignKey('SetOfProduct', on_delete=models.SET_NULL, null=True, blank=True,
                                        verbose_name='Выберите Комплект',
                                        related_name='products', related_query_name='products')

    objects = ProductQueryset.as_manager()

    def __str__(self):
        return self.name_ru

    def save(self, *args, **kwargs):
        if self.discounted_price > self.price:
            raise ValueError('скидочная цена не может быть меньше цены продукты!')

        return super(Product, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'


class ProductImage(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='product_images',
                                related_query_name='product_images', verbose_name='картинка продуктов')
    photo = models.ImageField(upload_to=product_image_directory_path, verbose_name='Фото продукта')

    def __str__(self):
        return '{}'.format(self.product.name_ru)

    class Meta:
        verbose_name = 'Картинка продукта'
        verbose_name_plural = 'Картинки продуктов'


class Review(BaseModel):
    full_name = models.CharField(max_length=100, verbose_name='Полное имя')
    rating = models.PositiveIntegerField(verbose_name='Рейтинг',
                                         validators=[MinValueValidator(1), MaxValueValidator(5)], default=5)
    comment = models.TextField(verbose_name='Комментария')

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', related_query_name='reviews',
                             verbose_name='Какому пользователю принадлежит отзыв', null=True)
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='reviews',
                                related_query_name='reviews', verbose_name='Какому продукту принадлежит отзыв')

    def __str__(self):
        return 'Пользователь: {0}, рейтинг: {1}'.format(self.full_name, self.rating)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']


class Basket(BaseModel):
    price = models.PositiveBigIntegerField(default=0, verbose_name='Общая сумма')
    quantity = models.PositiveBigIntegerField(verbose_name='Кол-во товара')

    user = models.ForeignKey(User, verbose_name='Кому принадлежит товар',
                             related_name='baskets', related_query_name='baskets', null=True, on_delete=models.SET_NULL)
    product = models.ForeignKey('Product', related_name='baskets', related_query_name='baskets', null=True,
                                on_delete=models.SET_NULL)
    order = models.ForeignKey('Order', related_name='baskets', related_query_name='baskets', on_delete=models.SET_NULL,
                              null=True, default=None)

    def save(self, *args, **kwargs):
        if self.product.discounted_price:
            self.price = self.quantity * (self.product.price - self.product.discounted_price)
            return super(Basket, self).save(*args, **kwargs)

        self.price = self.quantity * self.product.price
        return super(Basket, self).save(*args, **kwargs)

    def __str__(self):
        return self.__str__()

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'


class Favorite(BaseModel):
    user = models.ForeignKey(User, related_name='favorites',
                             related_query_name='favorites', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', related_name='favorites',
                                related_query_name='favorites', on_delete=models.CASCADE)

    def __str__(self):
        return '#{0}, {1} {2}'.format(self.pk, self.user.first_name, self.user.last_name)

    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранные'


class Order(BaseModel):
    DELIVERY_CHOICES = (
        ('dcb', 'Доставка по городу Бухара'),
        ('dtu', 'Доставка по всему Узбекистану'),
        ('pickup', 'Самовывоз'),
    )

    STATUS_CHOICES = (
        ('purchased', 'Куплен'),
        ('moderation', 'На модерации'),
    )

    total_price = models.PositiveBigIntegerField(default=0)
    type = models.CharField(max_length=100, choices=DELIVERY_CHOICES)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=13)
    email = models.EmailField()
    fix_check = models.FileField(upload_to=check_path)

    address = models.CharField(max_length=255, blank=True, null=True)

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='На модерации')
    order_code = models.CharField(max_length=10, unique=True)

    order_code_idx = models.Index(fields=['order_code'], name='order_code_idx')

    def __str__(self):
        return '#{0} - {1}'.format(self.order_code, self.full_name)

    def save(self, *args, **kwargs):
        self.order_code = random_code(length=10)

        if self.type == 'dtu' or self.type == 'Доставка по всему Узбекистану':
            self.total_price += Menu.objects.get(is_active=True).delivery_price

        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
