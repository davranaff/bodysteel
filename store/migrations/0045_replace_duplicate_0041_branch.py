from django.db import migrations, models


class Migration(migrations.Migration):
    """Replace the conflicting checkout branch for clean database installs."""

    replaces = [
        ("store", "0041_basket_product_name_ru_basket_product_name_uz_and_more"),
    ]

    dependencies = [
        ("store", "0040_rich_html_policy_v2"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer_note",
            field=models.CharField(blank=True, default="", max_length=1000),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_fee",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_method_code",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_slot_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_slot_label",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_zone_code",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="discount_price",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="order",
            name="subtotal_price",
            field=models.PositiveBigIntegerField(default=0),
        ),
    ]
