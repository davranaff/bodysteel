from django.core.validators import MinValueValidator
from django.db import models

from store.fields import SanitizedHtmlField


def course_cover_path(instance, filename):
    return 'courses/{}/covers/{}'.format(instance.slug, filename)


def lesson_image_path(instance, filename):
    return 'courses/{}/lessons/{}'.format(instance.module.course.slug, filename)


def lesson_material_path(instance, filename):
    return 'courses/{}/materials/{}'.format(instance.lesson.module.course.slug, filename)


class Course(models.Model):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'
    STATUS_CHOICES = (
        (DRAFT, 'Черновик'),
        (PUBLISHED, 'Опубликован'),
        (ARCHIVED, 'Архив'),
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name='Адрес курса (URL)',
        help_text='Уникальная часть ссылки латиницей, например: pravilnoe-pitanie.',
    )
    title_ru = models.CharField(max_length=255, verbose_name='Название на русском')
    title_uz = models.CharField(max_length=255, verbose_name='Название на узбекском')
    summary_ru = models.TextField(max_length=2000, verbose_name='Краткое описание на русском')
    summary_uz = models.TextField(max_length=2000, verbose_name='Краткое описание на узбекском')
    description_ru = SanitizedHtmlField(blank=True, default='', verbose_name='Полное описание на русском')
    description_uz = SanitizedHtmlField(blank=True, default='', verbose_name='Полное описание на узбекском')
    cover = models.ImageField(
        upload_to=course_cover_path,
        blank=True,
        null=True,
        verbose_name='Обложка курса',
    )
    price = models.PositiveBigIntegerField(validators=[MinValueValidator(0)], verbose_name='Цена')
    currency = models.CharField(max_length=3, default='UZS', verbose_name='Валюта')
    duration_days = models.PositiveIntegerField(default=30, verbose_name='Продолжительность курса, дней')
    estimated_minutes = models.PositiveIntegerField(default=0, verbose_name='Расчётная длительность, минут')
    access_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Срок доступа после покупки, дней',
        help_text='Оставьте пустым, чтобы доступ не был ограничен по времени.',
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=DRAFT,
        db_index=True,
        verbose_name='Статус',
    )
    sales_start_at = models.DateTimeField(null=True, blank=True, verbose_name='Начало продаж')
    sales_end_at = models.DateTimeField(null=True, blank=True, verbose_name='Окончание продаж')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата публикации')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        ordering = ('sort_order', '-created_at')
        indexes = [models.Index(fields=('status', 'sort_order'))]
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'

    def __str__(self):
        return self.title_ru

    def is_available_for_sale(self, now=None):
        from django.utils import timezone

        now = now or timezone.now()
        return (
            self.status == self.PUBLISHED
            and (self.sales_start_at is None or self.sales_start_at <= now)
            and (self.sales_end_at is None or self.sales_end_at >= now)
        )


class CourseModule(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules',
        verbose_name='Курс',
    )
    title_ru = models.CharField(max_length=255, verbose_name='Название на русском')
    title_uz = models.CharField(max_length=255, verbose_name='Название на узбекском')
    description_ru = models.TextField(
        max_length=2000,
        blank=True,
        default='',
        verbose_name='Описание на русском',
    )
    description_uz = models.TextField(
        max_length=2000,
        blank=True,
        default='',
        verbose_name='Описание на узбекском',
    )
    position = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')
    is_published = models.BooleanField(default=True, verbose_name='Опубликован')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        ordering = ('position', 'id')
        constraints = [models.UniqueConstraint(fields=('course', 'position'), name='course_module_position')]
        verbose_name = 'Модуль курса'
        verbose_name_plural = 'Модули курсов'

    def __str__(self):
        return '{} / {}'.format(self.course.title_ru, self.title_ru)


class Lesson(models.Model):
    module = models.ForeignKey(
        CourseModule,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name='Модуль курса',
    )
    title_ru = models.CharField(max_length=255, verbose_name='Название на русском')
    title_uz = models.CharField(max_length=255, verbose_name='Название на узбекском')
    text_ru = SanitizedHtmlField(blank=True, default='', verbose_name='Текст урока на русском')
    text_uz = SanitizedHtmlField(blank=True, default='', verbose_name='Текст урока на узбекском')
    image = models.ImageField(
        upload_to=lesson_image_path,
        blank=True,
        null=True,
        verbose_name='Изображение урока',
    )
    duration_minutes = models.PositiveIntegerField(default=0, verbose_name='Продолжительность, минут')
    position = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')
    is_preview = models.BooleanField(default=False, verbose_name='Доступен для предпросмотра')
    is_published = models.BooleanField(default=True, verbose_name='Опубликован')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        ordering = ('position', 'id')
        constraints = [models.UniqueConstraint(fields=('module', 'position'), name='lesson_module_position')]
        verbose_name = 'Урок'
        verbose_name_plural = 'Уроки'

    def __str__(self):
        return '{} / {}'.format(self.module.title_ru, self.title_ru)


class LessonMaterial(models.Model):
    KIND_CHOICES = (
        ('file', 'Файл'),
        ('image', 'Изображение'),
        ('video', 'Видео'),
        ('audio', 'Аудио'),
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name='Урок',
    )
    title_ru = models.CharField(max_length=255, verbose_name='Название на русском')
    title_uz = models.CharField(max_length=255, verbose_name='Название на узбекском')
    kind = models.CharField(max_length=40, choices=KIND_CHOICES, default='file', verbose_name='Тип материала')
    file = models.FileField(
        upload_to=lesson_material_path,
        blank=True,
        null=True,
        verbose_name='Файл',
    )
    external_url = models.URLField(max_length=1000, blank=True, default='', verbose_name='Внешняя ссылка')
    is_downloadable = models.BooleanField(default=True, verbose_name='Разрешить скачивание')
    position = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        ordering = ('position', 'id')
        verbose_name = 'Материал урока'
        verbose_name_plural = 'Материалы уроков'

    def __str__(self):
        return self.title_ru


# Access and purchase models live separately to keep this model module focused.
from courses.access_models import CourseAccess, CoursePurchase, LessonProgress  # noqa: E402,F401
