from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0040_rich_html_policy_v2"),
    ]

    operations = [
        migrations.AddField(
            model_name="basket",
            name="product_name_ru",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="basket",
            name="product_name_uz",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="basket",
            name="product_type",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="basket",
            name="unit_price",
            field=models.PositiveBigIntegerField(
                default=0, verbose_name="Цена за единицу на момент заказа"
            ),
        ),
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
            name="fulfillment_status",
            field=models.CharField(
                choices=[
                    ("new", "Новый"),
                    ("confirmed", "Подтверждён"),
                    ("preparing", "Готовится"),
                    ("ready", "Готов к выдаче"),
                    ("delivering", "В доставке"),
                    ("delivered", "Доставлен"),
                    ("cancelled", "Отменён"),
                ],
                db_index=True,
                default="new",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("unpaid", "Не оплачен"),
                    ("pending", "Ожидает оплаты"),
                    ("paid", "Оплачен"),
                    ("failed", "Ошибка оплаты"),
                    ("refunded", "Возвращён"),
                ],
                db_index=True,
                default="unpaid",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="subtotal_price",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="product",
            name="product_type",
            field=models.CharField(
                choices=[
                    ("supplement", "Спортивное питание"),
                    ("meal", "Готовое блюдо"),
                    ("meal_kit", "Набор правильного питания"),
                ],
                db_index=True,
                default="supplement",
                max_length=20,
                verbose_name="Тип физического товара",
            ),
        ),
    ]
