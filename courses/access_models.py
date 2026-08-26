from django.conf import settings
from django.db import models


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

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='course_purchases',
        verbose_name='Покупатель',
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name='Курс',
    )
    course_title = models.CharField(max_length=255, verbose_name='Название курса на момент покупки')
    amount = models.PositiveBigIntegerField(verbose_name='Сумма')
    currency = models.CharField(max_length=3, default='UZS', verbose_name='Валюта')
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=CREATED,
        db_index=True,
        verbose_name='Статус',
    )
    idempotency_digest = models.CharField(max_length=64, unique=True, verbose_name='Ключ защиты от дублирования')
    request_fingerprint = models.CharField(max_length=64, default='', verbose_name='Отпечаток запроса')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата оплаты')

    class Meta:
        indexes = [models.Index(fields=('user', 'status')), models.Index(fields=('course', 'status'))]
        verbose_name = 'Покупка курса'
        verbose_name_plural = 'Покупки курсов'

    def __str__(self):
        return '{} / {}'.format(self.user.username, self.course_title)


class CourseAccess(models.Model):
    ACTIVE = 'active'
    REVOKED = 'revoked'
    EXPIRED = 'expired'
    STATUS_CHOICES = ((ACTIVE, 'Активен'), (REVOKED, 'Отозван'), (EXPIRED, 'Истёк'))
    SOURCE_CHOICES = (('purchase', 'Покупка'), ('manual', 'Выдан вручную'))

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_accesses',
        verbose_name='Пользователь',
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.PROTECT,
        related_name='access_grants',
        verbose_name='Курс',
    )
    purchase = models.ForeignKey(
        'courses.CoursePurchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_grants',
        verbose_name='Покупка курса',
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='purchase',
        verbose_name='Источник доступа',
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=ACTIVE,
        db_index=True,
        verbose_name='Статус',
    )
    granted_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата выдачи доступа')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Доступ действует до')
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата отзыва доступа')
    revoke_reason = models.CharField(max_length=500, blank=True, default='', verbose_name='Причина отзыва')

    class Meta:
        constraints = [models.UniqueConstraint(fields=('user', 'course'), name='course_access_user_course')]
        indexes = [models.Index(fields=('user', 'status'))]
        verbose_name = 'Доступ к курсу'
        verbose_name_plural = 'Доступы к курсам'

    def __str__(self):
        return '{} / {}'.format(self.user.username, self.course.title_ru)

    def is_active(self):
        from django.utils import timezone

        return self.status == self.ACTIVE and (self.expires_at is None or self.expires_at > timezone.now())


class LessonProgress(models.Model):
    access = models.ForeignKey(
        CourseAccess,
        on_delete=models.CASCADE,
        related_name='progress',
        verbose_name='Доступ к курсу',
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='progress',
        verbose_name='Урок',
    )
    percent = models.PositiveSmallIntegerField(default=0, verbose_name='Пройдено, %')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата завершения')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        constraints = [models.UniqueConstraint(fields=('access', 'lesson'), name='lesson_progress_access_lesson')]
        verbose_name = 'Прогресс урока'
        verbose_name_plural = 'Прогресс уроков'
