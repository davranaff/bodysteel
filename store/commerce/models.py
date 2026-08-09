from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from store.content.models import Menu
from store.models import BaseModel, check_path
from users.models import User
from users.utils.random_code import random_code


class Basket(BaseModel):
    price = models.PositiveBigIntegerField(default=0, verbose_name='Общая сумма')
    quantity = models.PositiveBigIntegerField(verbose_name='Кол-во товара')
    user = models.ForeignKey(
        User,
        verbose_name='Кому принадлежит товар',
        related_name='baskets',
        related_query_name='baskets',
        null=True,
        on_delete=models.SET_NULL,
    )
    product = models.ForeignKey(
        'Product',
        related_name='baskets',
        related_query_name='baskets',
        null=True,
        on_delete=models.SET_NULL,
    )
    order = models.ForeignKey(
        'Order',
        related_name='baskets',
        related_query_name='baskets',
        on_delete=models.SET_NULL,
        null=True,
        default=None,
    )

    def save(self, *args, **kwargs):
        unit_price = self.product.price - self.product.discounted_price
        self.price = self.quantity * unit_price
        return super().save(*args, **kwargs)

    def __str__(self):
        identity = self.pk if self.pk is not None else 'new'
        return 'Корзина #{0}: товар {1}, количество {2}'.format(
            identity,
            self.product_id,
            self.quantity,
        )

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'


class Favorite(BaseModel):
    user = models.ForeignKey(
        User,
        related_name='favorites',
        related_query_name='favorites',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        'Product',
        related_name='favorites',
        related_query_name='favorites',
        on_delete=models.CASCADE,
    )

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

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='Пользователь',
        null=True,
        blank=True,
    )
    total_price = models.PositiveBigIntegerField(default=0)
    type = models.CharField(max_length=100, choices=DELIVERY_CHOICES)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=13)
    fix_check = models.FileField(upload_to=check_path, null=True)
    address = models.CharField(max_length=255, blank=True, null=True, default='')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='moderation')
    order_code = models.CharField(max_length=10, unique=True)
    idempotency_digest = models.CharField(max_length=64, unique=True, null=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, null=True, editable=False)
    coupon = models.ForeignKey(
        'Coupon',
        on_delete=models.SET_NULL,
        related_name='orders',
        verbose_name='Использованный купон',
        null=True,
        blank=True,
    )

    def __str__(self):
        return '#{0} - {1}'.format(self.order_code, self.full_name)

    def save(self, *args, **kwargs):
        adding = self._state.adding
        if not self.order_code:
            self.order_code = random_code(length=10)
        if adding and self.type in {'dtu', 'Доставка по всему Узбекистану'}:
            self.total_price += Menu.objects.get(is_active=True).delivery_price
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(idempotency_digest__isnull=True, request_fingerprint__isnull=True)
                    | models.Q(idempotency_digest__isnull=False, request_fingerprint__isnull=False)
                ),
                name='store_order_idempotency_pair',
            ),
        ]


class Coupon(BaseModel):
    code = models.CharField(max_length=20, unique=True, verbose_name='Код купона')
    discount_percent = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Процент скидки',
    )
    max_uses = models.PositiveIntegerField(default=1, verbose_name='Максимальное количество использований')
    used_count = models.PositiveIntegerField(default=0, verbose_name='Количество использований')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    def can_use(self):
        return self.is_active and self.used_count < self.max_uses

    def __str__(self):
        return '{0} - {1}%'.format(self.code, self.discount_percent)

    class Meta:
        verbose_name = 'Купон'
        verbose_name_plural = 'Купоны'
        ordering = ['-created_at']
