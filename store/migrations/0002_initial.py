# Generated by Django 5.0.2 on 2024-03-14 18:59

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('store', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='basket',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='baskets', related_query_name='baskets', to=settings.AUTH_USER_MODEL, verbose_name='Кому принадлежит товар'),
        ),
        migrations.AlterUniqueTogether(
            name='category',
            unique_together={('name_uz', 'name_ru', 'sort')},
        ),
        migrations.AddField(
            model_name='favorite',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', related_query_name='favorites', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='order',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', related_query_name='order', to=settings.AUTH_USER_MODEL, verbose_name='orders'),
        ),
        migrations.AddField(
            model_name='basket',
            name='order',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='baskets', related_query_name='baskets', to='store.order'),
        ),
        migrations.AddField(
            model_name='product',
            name='brand',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', related_query_name='products', to='store.brand', verbose_name='Бренд продукта'),
        ),
        migrations.AddField(
            model_name='product',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', related_query_name='products', to='store.category', verbose_name='Категория продукта'),
        ),
        migrations.AddField(
            model_name='favorite',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', related_query_name='favorites', to='store.product'),
        ),
        migrations.AddField(
            model_name='basket',
            name='product',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='baskets', related_query_name='baskets', to='store.product'),
        ),
        migrations.AddField(
            model_name='productimage',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_images', related_query_name='product_images', to='store.product', verbose_name='картинка продуктов'),
        ),
        migrations.AddField(
            model_name='review',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', related_query_name='reviews', to='store.product', verbose_name='Какому продукту принадлежит отзыв'),
        ),
        migrations.AddField(
            model_name='review',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reviews', related_query_name='reviews', to=settings.AUTH_USER_MODEL, verbose_name='Какому пользователю принадлежит отзыв'),
        ),
        migrations.AlterUniqueTogether(
            name='setofproduct',
            unique_together={('name_uz', 'name_ru')},
        ),
        migrations.AddField(
            model_name='product',
            name='set_of_products',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', related_query_name='products', to='store.setofproduct', verbose_name='Выберите Комплект'),
        ),
    ]
