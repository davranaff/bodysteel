from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from store.admin_site import bodysteel_admin_site
from store.models import Review


@admin.register(Review, site=bodysteel_admin_site)
class ReviewAdmin(admin.ModelAdmin):
    empty_value_display = '—'
    list_display = (
        'rating_badge', 'full_name', 'product', 'comment_preview', 'publication_badge',
        'open_report_count', 'created_at',
    )
    list_filter = ('is_published', 'rating', 'created_at')
    search_fields = ('full_name', 'comment', 'product__name_ru')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'moderated_at', 'moderated_by')
    list_select_related = ('product', 'user')
    actions = ('publish_reviews', 'unpublish_reviews')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            open_reports=Count('content_reports', filter=Q(content_reports__status='open')),
        )

    def save_model(self, request, obj, form, change):
        if 'is_published' in form.changed_data:
            obj.moderated_at = timezone.now()
            obj.moderated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Опубликовать выбранные отзывы', permissions=('change',))
    def publish_reviews(self, request, queryset):
        updated = self._moderate(request, queryset, True)
        self.message_user(request, f'Опубликовано отзывов: {updated}', messages.SUCCESS)

    @admin.action(description='Скрыть выбранные отзывы', permissions=('change',))
    def unpublish_reviews(self, request, queryset):
        updated = self._moderate(request, queryset, False)
        self.message_user(request, f'Скрыто отзывов: {updated}', messages.SUCCESS)

    @staticmethod
    def _moderate(request, queryset, published):
        return Review.objects.filter(pk__in=queryset.values('pk')).update(
            is_published=published,
            moderated_at=timezone.now(),
            moderated_by=request.user,
        )

    @admin.display(description='Оценка', ordering='rating')
    def rating_badge(self, obj):
        return format_html('<span class="bs-rating">{} <small>/ 5</small></span>', obj.rating)

    @admin.display(description='Комментарий')
    def comment_preview(self, obj):
        return (obj.comment or 'Без комментария')[:72]

    @admin.display(description='Публикация', ordering='is_published')
    def publication_badge(self, obj):
        if obj.is_published:
            return format_html('<span class="bs-status bs-status--success">{}</span>', 'Опубликован')
        return format_html('<span class="bs-status bs-status--danger">{}</span>', 'На модерации')

    @admin.display(description='Открытые жалобы', ordering='open_reports')
    def open_report_count(self, obj):
        return getattr(obj, 'open_reports', 0)
