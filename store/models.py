"""Stable Django model facade and historical migration callbacks."""

import unicodedata

from django.db import models


def category_directory_path(instance, filename):
    return _upload_path('categories', instance.name_ru, filename)


def blog_directory_path(instance, filename):
    return _upload_path('blog', instance.name_ru, filename)


def brand_directory_path(instance, filename):
    return _upload_path('brand', instance.name, filename)


def product_image_directory_path(instance, filename):
    return _upload_path('product_images', instance.product.name_ru, filename)


def check_path(instance, filename):
    return _upload_path('checks', instance.order_code, filename)


def product_360_directory_path(instance, filename):
    return _upload_path('product_360', instance.product.name_ru, filename)


def filial_image_directory_path(instance, filename):
    return _upload_path('filial', instance.filial.name_ru, filename)


def _upload_path(prefix, directory, filename):
    return '{0}/{1}/{2}'.format(
        prefix,
        _upload_component(directory, 'unnamed'),
        _upload_component(filename, 'file'),
    )


def _upload_component(value, fallback):
    normalized = unicodedata.normalize('NFKC', str(value or ''))
    visible = ''.join(
        character for character in normalized
        if not unicodedata.category(character).startswith('C')
    )
    flattened = visible.replace('/', ' ').replace('\\', ' ')
    return ' '.join(flattened.split()) or fallback


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        abstract = True


# These imports intentionally follow the stable callbacks above. Historical migrations
# resolve upload functions through store.models while feature modules consume the same API.
from store.content.models import (  # noqa: E402
    Blog,
    Brand,
    Filial,
    FilialPhoto,
    Menu,
    SetOfProduct,
)
from store.catalog.models import (  # noqa: E402
    Category,
    Product,
    Product360Image,
    ProductImage,
    Review,
)
from store.commerce.models import Basket, Coupon, Favorite, Order  # noqa: E402

__all__ = (
    'BaseModel',
    'Basket',
    'Blog',
    'Brand',
    'Category',
    'Coupon',
    'Favorite',
    'Filial',
    'FilialPhoto',
    'Menu',
    'Order',
    'Product',
    'Product360Image',
    'ProductImage',
    'Review',
    'SetOfProduct',
    'blog_directory_path',
    'brand_directory_path',
    'category_directory_path',
    'check_path',
    'filial_image_directory_path',
    'product_360_directory_path',
    'product_image_directory_path',
)
