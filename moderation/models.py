from django.conf import settings
from django.db import models
from django.db.models import Q


class ContentReport(models.Model):
    """A customer's report about a review or an AI assistant answer (UGC moderation)."""

    class Kind(models.TextChoices):
        REVIEW = 'review', 'Отзыв о товаре'
        AI_ANSWER = 'ai_answer', 'Ответ ИИ-ассистента'

    class Reason(models.TextChoices):
        INCORRECT = 'incorrect', 'Неверная информация'
        OFFENSIVE = 'offensive', 'Оскорбительный контент'
        SPAM = 'spam', 'Спам'
        OTHER = 'other', 'Другое'

    class Status(models.TextChoices):
        OPEN = 'open', 'Открыта'
        RESOLVED = 'resolved', 'Решена'
        DISMISSED = 'dismissed', 'Отклонена'

    COMMENT_MAX_LENGTH = 500
    EXCERPT_MAX_LENGTH = 2000

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='content_reports',
        verbose_name='Автор жалобы',
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, verbose_name='Тип контента')
    review = models.ForeignKey(
        'store.Review',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='content_reports',
        verbose_name='Отзыв',
    )
    reason = models.CharField(max_length=16, choices=Reason.choices, verbose_name='Причина')
    comment = models.CharField(
        max_length=COMMENT_MAX_LENGTH, blank=True, default='', verbose_name='Комментарий покупателя',
    )
    excerpt = models.TextField(
        max_length=EXCERPT_MAX_LENGTH, blank=True, default='', verbose_name='Фрагмент ответа ИИ',
    )
    conversation_id = models.UUIDField(null=True, blank=True, verbose_name='ID диалога ИИ')
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True,
        verbose_name='Статус',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата жалобы')
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Кто обработал',
    )
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата обработки')

    def __str__(self):
        return 'Жалоба #{0}: {1}'.format(self.pk or 'new', self.get_kind_display())

    class Meta:
        verbose_name = 'Жалоба на контент'
        verbose_name_plural = 'Жалобы на контент'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', '-created_at'], name='moderation_report_queue_idx')]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind='review') | Q(review__isnull=True),
                name='moderation_report_review_kind',
            ),
            # One open report per customer and review keeps repeated taps idempotent.
            models.UniqueConstraint(
                fields=['reporter', 'review'],
                condition=Q(status='open', review__isnull=False, reporter__isnull=False),
                name='moderation_report_open_once',
            ),
        ]
