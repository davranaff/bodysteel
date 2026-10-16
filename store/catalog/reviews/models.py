from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from store.models import BaseModel


class ReviewQuerySet(models.QuerySet):
    def published(self):
        """Reviews visible on public storefront and mobile surfaces."""
        return self.filter(is_published=True)


class Review(BaseModel):
    full_name = models.CharField(max_length=100, verbose_name='Полное имя')
    rating = models.PositiveIntegerField(
        verbose_name='Рейтинг',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
    )
    comment = models.TextField(verbose_name='Комментария')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
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
    # New customer reviews wait for staff approval (UGC pre-moderation).
    is_published = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Опубликован',
        help_text='Только опубликованные отзывы видны покупателям и учитываются в рейтинге',
    )
    moderated_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата модерации')
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Модератор',
    )

    objects = ReviewQuerySet.as_manager()

    def __str__(self):
        return 'Пользователь: {0}, рейтинг: {1}'.format(self.full_name, self.rating)

    class Meta:
        app_label = 'store'
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']
