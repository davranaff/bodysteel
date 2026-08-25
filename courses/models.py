from django.conf import settings
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

    slug = models.SlugField(max_length=255, unique=True)
    title_ru = models.CharField(max_length=255)
    title_uz = models.CharField(max_length=255)
    summary_ru = models.TextField(max_length=2000)
    summary_uz = models.TextField(max_length=2000)
    description_ru = SanitizedHtmlField(blank=True, default='')
    description_uz = SanitizedHtmlField(blank=True, default='')
    cover = models.ImageField(upload_to=course_cover_path, blank=True, null=True)
    price = models.PositiveBigIntegerField(validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='UZS')
    duration_days = models.PositiveIntegerField(default=30)
    estimated_minutes = models.PositiveIntegerField(default=0)
    access_duration_days = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT, db_index=True)
    sales_start_at = models.DateTimeField(null=True, blank=True)
    sales_end_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('sort_order', '-created_at')
        indexes = [models.Index(fields=('status', 'sort_order'))]

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
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title_ru = models.CharField(max_length=255)
    title_uz = models.CharField(max_length=255)
    description_ru = models.TextField(max_length=2000, blank=True, default='')
    description_uz = models.TextField(max_length=2000, blank=True, default='')
    position = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('position', 'id')
        constraints = [models.UniqueConstraint(fields=('course', 'position'), name='course_module_position')]

    def __str__(self):
        return '{} / {}'.format(self.course.title_ru, self.title_ru)


class Lesson(models.Model):
    module = models.ForeignKey(CourseModule, on_delete=models.CASCADE, related_name='lessons')
    title_ru = models.CharField(max_length=255)
    title_uz = models.CharField(max_length=255)
    text_ru = SanitizedHtmlField(blank=True, default='')
    text_uz = SanitizedHtmlField(blank=True, default='')
    image = models.ImageField(upload_to=lesson_image_path, blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    position = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('position', 'id')
        constraints = [models.UniqueConstraint(fields=('module', 'position'), name='lesson_module_position')]

    def __str__(self):
        return '{} / {}'.format(self.module.title_ru, self.title_ru)


class LessonMaterial(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='materials')
    title_ru = models.CharField(max_length=255)
    title_uz = models.CharField(max_length=255)
    kind = models.CharField(max_length=40, default='file')
    file = models.FileField(upload_to=lesson_material_path, blank=True, null=True)
    external_url = models.URLField(max_length=1000, blank=True, default='')
    is_downloadable = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('position', 'id')

    def __str__(self):
        return self.title_ru


class CoursePurchase(models.Model):
    CREATED = 'created'
    PENDING = 'payment_pending'
    PAID = 'paid'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'
    STATUS_CHOICES = (
        (CREATED, 'Создана'),
        (PENDING, 'Ожидает оплаты'),
        (PAID, 'Оплачена'),
        (CANCELLED, 'Отменена'),
        (REFUNDED, 'Возвращена'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='course_purchases')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='purchases')
    course_title = models.CharField(max_length=255)
    amount = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default='UZS')
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=CREATED, db_index=True)
    idempotency_digest = models.CharField(max_length=64, unique=True)
    request_fingerprint = models.CharField(max_length=64, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=('user', 'status')), models.Index(fields=('course', 'status'))]

    def __str__(self):
        return '{} / {}'.format(self.user.username, self.course_title)


class CourseAccess(models.Model):
    ACTIVE = 'active'
    REVOKED = 'revoked'
    EXPIRED = 'expired'
    STATUS_CHOICES = ((ACTIVE, 'Активен'), (REVOKED, 'Отозван'), (EXPIRED, 'Истёк'))

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_accesses')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='access_grants')
    purchase = models.ForeignKey(CoursePurchase, on_delete=models.SET_NULL, null=True, blank=True, related_name='access_grants')
    source = models.CharField(max_length=20, default='purchase')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE, db_index=True)
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        constraints = [models.UniqueConstraint(fields=('user', 'course'), name='course_access_user_course')]
        indexes = [models.Index(fields=('user', 'status'))]

    def __str__(self):
        return '{} / {}'.format(self.user.username, self.course.title_ru)

    def is_active(self):
        from django.utils import timezone

        return self.status == self.ACTIVE and (self.expires_at is None or self.expires_at > timezone.now())


class LessonProgress(models.Model):
    access = models.ForeignKey(CourseAccess, on_delete=models.CASCADE, related_name='progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress')
    percent = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('access', 'lesson'), name='lesson_progress_access_lesson')]
