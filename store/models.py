"""Stable Django model facade and historical migration callbacks."""

from django.db import models


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


def product_360_directory_path(instance, filename):
    return 'product_360/{0}/{1}'.format(instance.product.name_ru, filename)


def filial_image_directory_path(instance, filename):
    return 'filial/{0}/{1}'.format(instance.filial.name_ru, filename)


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
