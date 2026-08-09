from django.db import models

from store.fields import SanitizedHtmlField
from store.models import (
    BaseModel,
    blog_directory_path,
    brand_directory_path,
    filial_image_directory_path,
)


class Menu(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name='Дайте название для этого меню')
    about_uz = SanitizedHtmlField(verbose_name='О нас', help_text='Текст для раздела о нас uz')
    about_ru = SanitizedHtmlField(verbose_name='О нас', help_text='Текст для раздела о нас ru')
    blog_uz = SanitizedHtmlField(verbose_name='Блог', help_text='Текст для раздела Блог uz')
    blog_ru = SanitizedHtmlField(verbose_name='Блог', help_text='Текст для раздела Блог ru')
    set_product_uz = SanitizedHtmlField(verbose_name='Комплект', help_text='Текст для раздела Комплект uz')
    set_product_ru = SanitizedHtmlField(verbose_name='Комплект', help_text='Текст для раздела Комплект ru')
    delivery_and_payment_uz = SanitizedHtmlField(
        verbose_name='Доставка и Оплата uz',
        help_text='Текст для раздела Доставка и Оплата',
    )
    delivery_and_payment_ru = SanitizedHtmlField(
        verbose_name='Доставка и Оплата ru',
        help_text='Текст для раздела Доставка и Оплата',
    )
    delivery_price = models.IntegerField(verbose_name='Цена Доставки', default=0)
    bank_card_number = models.CharField(
        max_length=16,
        verbose_name='Номер Банковской карты',
        help_text='0000 0000 0000 0000',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активировать',
        help_text='Если отключено, то не будет видно',
        unique=True,
    )
    uzbekistan_description_uz = SanitizedHtmlField(
        verbose_name='Описание (Доставка по узб.) uz',
        null=True,
    )
    bukhara_description_uz = SanitizedHtmlField(
        verbose_name='Описание (Доставка по Бухаре) uz',
        null=True,
    )
    uzbekistan_description_ru = SanitizedHtmlField(
        verbose_name='Описание (Доставка по узб.) ru',
        null=True,
    )
    bukhara_description_ru = SanitizedHtmlField(
        verbose_name='Описание (Доставка по Бухаре) ru',
        null=True,
    )
    bonus = models.PositiveBigIntegerField(default=0, verbose_name='Бонусная цена')

    def __str__(self):
        return self.about_ru

    class Meta:
        verbose_name = 'Меню'
        verbose_name_plural = 'Меню'


class Filial(BaseModel):
    name_uz = models.CharField(max_length=100, verbose_name='Название филиала uz')
    name_ru = models.CharField(max_length=100, verbose_name='Название филиала ru')
    address_uz = models.CharField(
        max_length=255,
        verbose_name='Адрес филиала (без ссылки) uz',
        help_text=(
            'Адрес филиала, а не ссылка '
            '(Рес. Узбекистан, г. Бухара, ул. Абдулла кодирий 100 дом)'
        ),
    )
    address_ru = models.CharField(
        max_length=255,
        verbose_name='Адрес филиала (без ссылки) ru',
        help_text=(
            'Адрес филиала, а не ссылка '
            '(Рес. Узбекистан, г. Бухара, ул. Абдулла кодирий 100 дом)'
        ),
    )
    work_time_start = models.TimeField(verbose_name='Время старта работы', help_text='от ПН. до СБ.')
    work_time_end = models.TimeField(verbose_name='Время заканчиваие работы', help_text='от ПН. до СБ.')
    day_off = models.CharField(
        max_length=255,
        verbose_name='Выходной',
        help_text=(
            'Если вы работаете в выходные дни, то пишите время с какого часа до какого вы работаете, '
            'если нет то пишилте Выходной'
        ),
    )
    phone = models.CharField(max_length=13, verbose_name='Телефон номер филиала')
    address_url = models.TextField(verbose_name='Адрес филиала (только ссылка)')
    address_location = models.TextField(verbose_name='Локация филиала (только ссылка)', default=None)
    photo = models.ImageField(
        upload_to='filial/',
        verbose_name='Фотография филиала',
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name_ru

    class Meta:
        verbose_name = 'Филиал'
        verbose_name_plural = 'Филиалы'


class FilialPhoto(BaseModel):
    filial = models.ForeignKey(
        'Filial',
        on_delete=models.CASCADE,
        related_name='photos',
        related_query_name='photos',
        verbose_name='Филиал',
    )
    photo = models.ImageField(upload_to=filial_image_directory_path, verbose_name='Фотография филиала')

    def __str__(self):
        return '{0} - фото #{1}'.format(self.filial.name_ru, self.pk)

    class Meta:
        verbose_name = 'Фото филиала'
        verbose_name_plural = 'Фото филиалов'
        ordering = ['created_at', 'id']


class SetOfProduct(BaseModel):
    name_uz = models.CharField(max_length=255, verbose_name='Название комплекта uz')
    name_ru = models.CharField(max_length=255, verbose_name='Название комплекта ru')
    slug = models.SlugField(verbose_name='без пробела, либо через "-", либо через "_"', null=True)
    photo = models.ImageField(upload_to='set/%Y/%m/%d', verbose_name='Картинка комплекта')

    def __str__(self):
        return self.name_ru

    class Meta:
        verbose_name = 'Комплект'
        verbose_name_plural = 'Комплекты'
        unique_together = ('name_uz', 'name_ru')


class Blog(BaseModel):
    name_uz = models.CharField(max_length=255, verbose_name='Название блога uz', unique=True)
    name_ru = models.CharField(max_length=255, verbose_name='Название блога ru', unique=True)
    photo = models.ImageField(upload_to=blog_directory_path, verbose_name='Картинка блога')
    description_uz = SanitizedHtmlField(verbose_name='Описание блога uz')
    description_ru = SanitizedHtmlField(verbose_name='Описание блога ru')
    slug = models.SlugField(verbose_name='без пробела, либо через "-", либо через "_"', null=True)

    def __str__(self):
        return self.name_ru

    class Meta:
        verbose_name = 'Блог'
        verbose_name_plural = 'Блоги'


class Brand(BaseModel):
    name = models.CharField(max_length=100, verbose_name='Название бренда', unique=True)
    photo = models.ImageField(upload_to=brand_directory_path, verbose_name='Фотография бренда')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'
