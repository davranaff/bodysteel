# Generated by Django 5.0.2 on 2024-04-17 11:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0007_menu_bank_card_number_menu_delivery_price'),
    ]

    operations = [
        migrations.AlterField(
            model_name='filial',
            name='address_url',
            field=models.TextField(verbose_name='Адрес филиала (только ссылка)'),
        ),
    ]
