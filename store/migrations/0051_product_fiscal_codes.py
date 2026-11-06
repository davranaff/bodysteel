from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0050_catalog_image_size_limit"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="ikpu_code",
            field=models.CharField(
                blank=True,
                default="",
                help_text="17-значный код из tasnif.soliq.uz для фискального чека онлайн-оплаты.",
                max_length=17,
                verbose_name="ИКПУ (MXIK)",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="package_code",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Код упаковки из tasnif.soliq.uz для фискального чека онлайн-оплаты.",
                max_length=20,
                verbose_name="Код упаковки",
            ),
        ),
    ]
