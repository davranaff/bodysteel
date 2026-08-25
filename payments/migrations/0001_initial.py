import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("courses", "0001_initial"),
        ("store", "0041_basket_product_name_ru_basket_product_name_uz_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "provider",
                    models.CharField(db_index=True, default="manual", max_length=40),
                ),
                (
                    "provider_payment_id",
                    models.CharField(
                        blank=True, max_length=255, null=True, unique=True
                    ),
                ),
                ("amount", models.PositiveBigIntegerField()),
                ("currency", models.CharField(default="UZS", max_length=3)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Создан"),
                            ("pending", "Ожидает оплаты"),
                            ("succeeded", "Успешен"),
                            ("failed", "Ошибка"),
                            ("cancelled", "Отменён"),
                            ("refunded", "Возвращён"),
                        ],
                        db_index=True,
                        default="created",
                        max_length=16,
                    ),
                ),
                (
                    "idempotency_digest",
                    models.CharField(blank=True, max_length=64, null=True, unique=True),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                (
                    "course_purchase",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="courses.coursepurchase",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="store.order",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("provider", models.CharField(max_length=40)),
                ("external_event_id", models.CharField(max_length=255)),
                ("event_type", models.CharField(max_length=100)),
                ("payload_hash", models.CharField(max_length=64)),
                (
                    "processing_status",
                    models.CharField(default="received", max_length=20),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="payments.payment",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("course_purchase__isnull", True), ("order__isnull", False)
                    ),
                    models.Q(
                        ("course_purchase__isnull", False), ("order__isnull", True)
                    ),
                    _connector="OR",
                ),
                name="payment_exactly_one_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentevent",
            constraint=models.UniqueConstraint(
                fields=("provider", "external_event_id"),
                name="payment_event_provider_external_id",
            ),
        ),
    ]
