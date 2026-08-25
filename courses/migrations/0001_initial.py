import courses.models
import django.core.validators
import django.db.models.deletion
import store.fields
from django.conf import settings
from django.db import migrations, models


def legacy_lesson_video_path(instance, filename):
    return "courses/{}/videos/{}".format(instance.module.course.slug, filename)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Course",
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
                ("slug", models.SlugField(max_length=255, unique=True)),
                ("title_ru", models.CharField(max_length=255)),
                ("title_uz", models.CharField(max_length=255)),
                ("summary_ru", models.TextField(max_length=2000)),
                ("summary_uz", models.TextField(max_length=2000)),
                (
                    "description_ru",
                    store.fields.SanitizedHtmlField(blank=True, default=""),
                ),
                (
                    "description_uz",
                    store.fields.SanitizedHtmlField(blank=True, default=""),
                ),
                (
                    "cover",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to=courses.models.course_cover_path,
                    ),
                ),
                (
                    "price",
                    models.PositiveBigIntegerField(
                        validators=[django.core.validators.MinValueValidator(0)]
                    ),
                ),
                ("currency", models.CharField(default="UZS", max_length=3)),
                ("duration_days", models.PositiveIntegerField(default=30)),
                ("estimated_minutes", models.PositiveIntegerField(default=0)),
                (
                    "access_duration_days",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Черновик"),
                            ("published", "Опубликован"),
                            ("archived", "Архив"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("sales_start_at", models.DateTimeField(blank=True, null=True)),
                ("sales_end_at", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("sort_order", "-created_at"),
                "indexes": [
                    models.Index(
                        fields=["status", "sort_order"],
                        name="courses_cou_status_d65d98_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="CourseModule",
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
                ("title_ru", models.CharField(max_length=255)),
                ("title_uz", models.CharField(max_length=255)),
                (
                    "description_ru",
                    models.TextField(blank=True, default="", max_length=2000),
                ),
                (
                    "description_uz",
                    models.TextField(blank=True, default="", max_length=2000),
                ),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="modules",
                        to="courses.course",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
            },
        ),
        migrations.CreateModel(
            name="CoursePurchase",
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
                ("course_title", models.CharField(max_length=255)),
                ("amount", models.PositiveBigIntegerField()),
                ("currency", models.CharField(default="UZS", max_length=3)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Создана"),
                            ("payment_pending", "Ожидает оплаты"),
                            ("paid", "Оплачена"),
                            ("cancelled", "Отменена"),
                            ("refunded", "Возвращена"),
                        ],
                        db_index=True,
                        default="created",
                        max_length=24,
                    ),
                ),
                ("idempotency_digest", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchases",
                        to="courses.course",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="course_purchases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CourseAccess",
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
                ("source", models.CharField(default="purchase", max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Активен"),
                            ("revoked", "Отозван"),
                            ("expired", "Истёк"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=16,
                    ),
                ),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "revoke_reason",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="access_grants",
                        to="courses.course",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_accesses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "purchase",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="access_grants",
                        to="courses.coursepurchase",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Lesson",
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
                ("title_ru", models.CharField(max_length=255)),
                ("title_uz", models.CharField(max_length=255)),
                ("text_ru", store.fields.SanitizedHtmlField(blank=True, default="")),
                ("text_uz", store.fields.SanitizedHtmlField(blank=True, default="")),
                (
                    "video_type",
                    models.CharField(
                        choices=[
                            ("none", "Без видео"),
                            ("external", "Внешний провайдер"),
                            ("file", "Приватный файл"),
                        ],
                        default="none",
                        max_length=16,
                    ),
                ),
                (
                    "video_reference",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                (
                    "video_file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=legacy_lesson_video_path,
                    ),
                ),
                ("duration_minutes", models.PositiveIntegerField(default=0)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_preview", models.BooleanField(default=False)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "module",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lessons",
                        to="courses.coursemodule",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
            },
        ),
        migrations.CreateModel(
            name="LessonMaterial",
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
                ("title_ru", models.CharField(max_length=255)),
                ("title_uz", models.CharField(max_length=255)),
                ("kind", models.CharField(default="file", max_length=40)),
                (
                    "file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=courses.models.lesson_material_path,
                    ),
                ),
                (
                    "external_url",
                    models.URLField(blank=True, default="", max_length=1000),
                ),
                ("is_downloadable", models.BooleanField(default=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="materials",
                        to="courses.lesson",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
            },
        ),
        migrations.CreateModel(
            name="LessonProgress",
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
                ("percent", models.PositiveSmallIntegerField(default=0)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "access",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress",
                        to="courses.courseaccess",
                    ),
                ),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress",
                        to="courses.lesson",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="coursemodule",
            constraint=models.UniqueConstraint(
                fields=("course", "position"), name="course_module_position"
            ),
        ),
        migrations.AddIndex(
            model_name="coursepurchase",
            index=models.Index(
                fields=["user", "status"], name="courses_cou_user_id_f92865_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="coursepurchase",
            index=models.Index(
                fields=["course", "status"], name="courses_cou_course__5c501c_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="courseaccess",
            index=models.Index(
                fields=["user", "status"], name="courses_cou_user_id_c091a9_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="courseaccess",
            constraint=models.UniqueConstraint(
                fields=("user", "course"), name="course_access_user_course"
            ),
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.UniqueConstraint(
                fields=("module", "position"), name="lesson_module_position"
            ),
        ),
        migrations.AddConstraint(
            model_name="lessonprogress",
            constraint=models.UniqueConstraint(
                fields=("access", "lesson"), name="lesson_progress_access_lesson"
            ),
        ),
    ]
