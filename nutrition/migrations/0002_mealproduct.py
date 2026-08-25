from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("nutrition", "0001_initial"),
        ("store", "0041_basket_product_name_ru_basket_product_name_uz_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MealProduct",
            fields=[],
            options={
                "verbose_name": "Блюдо правильного питания",
                "verbose_name_plural": "Правильное питание",
                "managed": False,
                "proxy": True,
            },
            bases=("store.product",),
        ),
    ]
