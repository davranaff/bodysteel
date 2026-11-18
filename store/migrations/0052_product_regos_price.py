from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0051_product_fiscal_codes"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="regos_price",
            field=models.PositiveBigIntegerField(
                blank=True,
                editable=False,
                help_text="Последняя розничная цена из REGOS. Цена на сайте меняется, когда меняется эта цена или карточка в REGOS.",
                null=True,
                verbose_name="Цена в REGOS",
            ),
        ),
    ]
