import django.db.models.deletion
import store.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("store", "0041_basket_product_name_ru_basket_product_name_uz_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Allergen",
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
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("name_ru", models.CharField(max_length=100)),
                ("name_uz", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="DeliveryMethod",
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
                ("code", models.SlugField(unique=True)),
                ("name_ru", models.CharField(max_length=100)),
                ("name_uz", models.CharField(max_length=100)),
                (
                    "kind",
                    models.CharField(
                        choices=[("courier", "Курьер"), ("pickup", "Самовывоз")],
                        default="courier",
                        max_length=20,
                    ),
                ),
                ("base_fee", models.PositiveBigIntegerField(default=0)),
                ("minimum_order", models.PositiveBigIntegerField(default=0)),
                ("free_from", models.PositiveBigIntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="DeliveryZone",
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
                ("code", models.SlugField(max_length=100, unique=True)),
                ("name_ru", models.CharField(max_length=150)),
                ("name_uz", models.CharField(max_length=150)),
                ("fee", models.PositiveBigIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="FoodTag",
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
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("name_ru", models.CharField(max_length=100)),
                ("name_uz", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="NutritionProfile",
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
                    "kind",
                    models.CharField(
                        choices=[("dish", "Блюдо"), ("meal_kit", "Набор")],
                        default="dish",
                        max_length=20,
                    ),
                ),
                ("portion_weight_grams", models.PositiveIntegerField(default=0)),
                ("servings", models.PositiveIntegerField(default=1)),
                ("calories_kcal", models.PositiveIntegerField(default=0)),
                (
                    "protein_grams",
                    models.DecimalField(decimal_places=2, default=0, max_digits=7),
                ),
                (
                    "fat_grams",
                    models.DecimalField(decimal_places=2, default=0, max_digits=7),
                ),
                (
                    "carbohydrate_grams",
                    models.DecimalField(decimal_places=2, default=0, max_digits=7),
                ),
                ("shelf_life_hours", models.PositiveIntegerField(default=0)),
                ("storage_ru", store.fields.SanitizedHtmlField(blank=True, default="")),
                ("storage_uz", store.fields.SanitizedHtmlField(blank=True, default="")),
                ("serving_ru", store.fields.SanitizedHtmlField(blank=True, default="")),
                ("serving_uz", store.fields.SanitizedHtmlField(blank=True, default="")),
                ("requires_cooling", models.BooleanField(default=False)),
                ("is_available", models.BooleanField(default=True)),
                (
                    "allergens",
                    models.ManyToManyField(
                        blank=True,
                        related_name="nutrition_profiles",
                        to="nutrition.allergen",
                    ),
                ),
                (
                    "allowed_delivery_methods",
                    models.ManyToManyField(
                        blank=True,
                        related_name="nutrition_profiles",
                        to="nutrition.deliverymethod",
                    ),
                ),
                (
                    "product",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nutrition_profile",
                        to="store.product",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="nutrition_profiles",
                        to="nutrition.foodtag",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="DeliverySlot",
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
                ("delivery_date", models.DateField()),
                ("starts_at", models.TimeField()),
                ("ends_at", models.TimeField()),
                ("cutoff_at", models.DateTimeField(blank=True, null=True)),
                ("capacity", models.PositiveIntegerField(default=0)),
                ("reserved_count", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "zone",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slots",
                        to="nutrition.deliveryzone",
                    ),
                ),
            ],
            options={
                "ordering": ("delivery_date", "starts_at"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("zone", "delivery_date", "starts_at", "ends_at"),
                        name="delivery_slot_identity",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="MealKitItem",
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
                ("quantity", models.PositiveIntegerField(default=1)),
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "component",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="included_in_kits",
                        to="store.product",
                    ),
                ),
                (
                    "kit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kit_items",
                        to="store.product",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("kit", "component"), name="meal_kit_component_unique"
                    )
                ],
            },
        ),
    ]
