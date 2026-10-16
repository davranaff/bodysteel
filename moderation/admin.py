from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from moderation.models import ContentReport
from moderation.services import close_reports
from store.admin_site import admin_url, bodysteel_admin_site
from store.models import Review


STATUS_TONES = {
    ContentReport.Status.OPEN: 'danger',
    ContentReport.Status.RESOLVED: 'success',
    ContentReport.Status.DISMISSED: 'muted',
}


@admin.register(ContentReport, site=bodysteel_admin_site)
class ContentReportAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    list_display = ('id', 'kind', 'reason', 'status_badge', 'review_link', 'content_preview', 'created_at')
    list_filter = ('status', 'kind', 'reason', 'created_at')
    search_fields = ('comment', 'excerpt', 'review__comment', 'review__product__name_ru')
    date_hierarchy = 'created_at'
    list_select_related = ('review', 'review__product')
    ordering = ('-created_at',)
    actions = ('resolve_reports', 'resolve_and_hide_reviews', 'dismiss_reports')
    readonly_fields = (
        'reporter', 'kind', 'review', 'review_link', 'reason', 'comment', 'excerpt',
        'conversation_id', 'created_at', 'status', 'resolved_by', 'resolved_at',
    )
    fields = readonly_fields

    def has_add_permission(self, request):
        # Reports come only from customers through the API.
        return False

    @admin.action(description='Отметить как решённые', permissions=('change',))
    def resolve_reports(self, request, queryset):
        updated = close_reports(queryset, ContentReport.Status.RESOLVED, request.user)
        self.message_user(request, f'Решено жалоб: {updated}', messages.SUCCESS)

    @admin.action(description='Скрыть отзывы и отметить жалобы решёнными', permissions=('change',))
    def resolve_and_hide_reviews(self, request, queryset):
        review_ids = queryset.filter(review__isnull=False).values('review_id')
        hidden = Review.objects.filter(pk__in=review_ids).update(
            is_published=False, moderated_at=timezone.now(), moderated_by=request.user,
        )
        updated = close_reports(queryset, ContentReport.Status.RESOLVED, request.user)
        self.message_user(request, f'Скрыто отзывов: {hidden}; решено жалоб: {updated}', messages.SUCCESS)

    @admin.action(description='Отклонить жалобы', permissions=('change',))
    def dismiss_reports(self, request, queryset):
        updated = close_reports(queryset, ContentReport.Status.DISMISSED, request.user)
        self.message_user(request, f'Отклонено жалоб: {updated}', messages.SUCCESS)

    @admin.display(description='Статус', ordering='status')
    def status_badge(self, obj):
        tone = STATUS_TONES.get(obj.status, 'muted')
        return format_html('<span class="bs-status bs-status--{}">{}</span>', tone, obj.get_status_display())

    @admin.display(description='Отзыв')
    def review_link(self, obj):
        if obj.review_id is None:
            return '—'
        url = admin_url(Review, 'change', obj.review_id)
        state = 'опубликован' if obj.review.is_published else 'скрыт'
        return format_html('<a href="{}">#{}</a> · {}', url, obj.review_id, state)

    @admin.display(description='Содержимое')
    def content_preview(self, obj):
        source = obj.excerpt if obj.kind == ContentReport.Kind.AI_ANSWER else getattr(obj.review, 'comment', '')
        return (source or '—')[:72]
