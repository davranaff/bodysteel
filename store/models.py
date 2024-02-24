from ckeditor.fields import RichTextField
from django.db import models


def category_directory_path(instance, filename):
    return 'categories/{0}/{1}'.format(instance.name, filename)


def blog_directory_path(instance, filename):
    return 'blog/{0}/{1}'.format(instance.name, filename)


def brand_directory_path(instance, filename):
    return 'brand/{0}/{1}'.format(instance.name, filename)


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Menu(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name='Дайте название для этого меню')

    about = RichTextField(verbose_name='О нас', help_text='Текст для раздела о нас')
    blog = RichTextField(verbose_name='Блог', help_text='Текст для раздела Блог')
    set_product = RichTextField(verbose_name='Комплект', help_text='Текст для раздела Комплект')
    delivery_and_payment = RichTextField(verbose_name='Доставка и Оплата',
                                         help_text='Текст для раздела Доставка и Оплата')

    is_active = models.BooleanField(default=True, verbose_name='Активировать',
                                    help_text='Если отключено, то не будет видно', unique=True)

    def __str__(self):
        return self.about

    class Meta:
        verbose_name = 'Меню'
        verbose_name_plural = 'Меню'


class Filial(BaseModel):
    name = models.CharField(max_length=100, verbose_name='Название филиала')
    address = models.CharField(max_length=255, verbose_name='Адрес филиала (без ссылки)',
                               help_text='Адрес филиала, а не ссылка (Рес. Узбекистан, г. Бухара, ул. Абдулла кодирий 100 дом)')

    work_time_start = models.TimeField(verbose_name='Время старта работы', help_text='от ПН. до СБ.')
    work_time_end = models.TimeField(verbose_name='Время заканчиваие работы', help_text='от ПН. до СБ.')

    day_off = models.CharField(max_length=255, verbose_name='Выходной',
                               help_text='Если вы работаете в выходные дни, то пишите время с какого часа до какого вы работаете, если нет то пишилте Выходной')

    phone = models.CharField(max_length=13, verbose_name='Телефон номер филиала')

    address_url = models.URLField(verbose_name='Адрес филиала (только ссылка)')

    photo = models.ImageField(upload_to='filial/', verbose_name='Фотография филиала')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Филиал'
        verbose_name_plural = 'Филиалы'


class SetOfProducts(BaseModel):
    name = models.CharField(max_length=255, verbose_name="Название комплекта", null=False, blank=False)
    photo = models.ImageField(upload_to='set/%Y/%m/%d', verbose_name="Картинка комплекта", null=False, blank=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Комплект"
        verbose_name_plural = "Комплекты"
        unique_together = ('name',)


class Category(BaseModel):
    name = models.CharField(max_length=255, verbose_name="Название категории", null=False, blank=False)
    photo = models.ImageField(upload_to=category_directory_path, verbose_name="Картинка категории", null=False,
                              blank=False)
    sort = models.PositiveIntegerField(verbose_name="Сортировка Категории",
                                       help_text='сортируется по возрастанию, у каждой категории должен быть уникальный номер',
                                       null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        unique_together = ('name', 'sort')


class Blog(BaseModel):
    name = models.CharField(max_length=255, verbose_name="Название блога", unique=True, null=False, blank=False)
    photo = models.ImageField(upload_to=category_directory_path, verbose_name="Картинка блога", null=False, blank=False)

    description = RichTextField(verbose_name="Описание блога", null=False, blank=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Блог"
        verbose_name_plural = "Блоги"


class Brand(BaseModel):
    name = models.CharField(max_length=100, verbose_name="Название бренда", unique=True)
    photo = models.ImageField(upload_to=blog_directory_path, verbose_name="Фотография бренда")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"


class Product(BaseModel):
    name = models.CharField(max_length=100, verbose_name='Название Продукта', unique=True)
    description = RichTextField(verbose_name='Описание Товара')

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

    slug = models.SlugField(max_length=255, unique=True)

    composition = RichTextField(verbose_name='Состав продукта')
    view_count = models.PositiveIntegerField(default=0, verbose_name='Кол-во. просмотров')

    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name='Категория продукта',
                                 related_name='products', related_query_name='products')

    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, verbose_name='Бренд продукта', related_name='products',
                              related_query_name='products')


