# Generated by Django 5.0.2 on 2024-05-16 00:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0020_remove_product_category_product_category'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='set_of_products',
        ),
        migrations.AddField(
            model_name='product',
            name='set_of_products',
            field=models.ManyToManyField(blank=True, null=True, related_name='products', related_query_name='products', to='store.setofproduct', verbose_name='Выберите Комплект'),
        ),
    ]
