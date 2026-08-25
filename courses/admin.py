from django.contrib import admin
from django.contrib import messages
from django.db.models import Max
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
import mimetypes
import os

from courses.forms import LessonMaterialUploadForm
from courses.models import Course, CourseAccess, CourseModule, CoursePurchase, Lesson, LessonMaterial, LessonProgress
from store.admin_site import bodysteel_admin_site, format_uzs


class CourseModuleInline(admin.TabularInline):
    model = CourseModule
    extra = 0
    ordering = ('position',)
    fields = ('position', 'title_ru', 'title_uz', 'is_published')


class LessonMaterialInline(admin.TabularInline):
    model = LessonMaterial
    extra = 0
    ordering = ('position',)
    fields = ('position', 'title_ru', 'title_uz', 'kind', 'file', 'external_url', 'is_downloadable')


@admin.register(Course, site=bodysteel_admin_site)
class CourseAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('title_ru', 'price_display', 'status', 'duration_days', 'buyers', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title_ru', 'title_uz', 'slug')
    prepopulated_fields = {'slug': ('title_ru',)}
    readonly_fields = ('created_at', 'updated_at', 'published_at')
    inlines = (CourseModuleInline,)
    fieldsets = (
        ('Карточка', {'fields': (('title_ru', 'title_uz'), 'slug', 'cover', ('summary_ru', 'summary_uz'), ('description_ru', 'description_uz'))}),
        ('Продажа', {'fields': (('price', 'currency'), ('duration_days', 'estimated_minutes'), 'access_duration_days', ('status', 'sales_start_at', 'sales_end_at'))}),
        ('Порядок', {'fields': ('sort_order', 'published_at', 'created_at', 'updated_at')}),
    )

    @admin.display(description='Цена')
    def price_display(self, obj):
        return format_uzs(obj.price)

    @admin.display(description='Покупатели')
    def buyers(self, obj):
        return obj.purchases.filter(status=CoursePurchase.PAID).count()

    def delete_model(self, request, obj):
        if obj.purchases.exists() or obj.access_grants.exists():
            obj.status = Course.ARCHIVED
            obj.save(update_fields=('status', 'updated_at'))
            self.message_user(request, 'Курс архивирован: у него есть покупки или доступы.')
            return
        super().delete_model(request, obj)


@admin.register(CourseModule, site=bodysteel_admin_site)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ('title_ru', 'course', 'position', 'is_published')
    list_filter = ('is_published', 'course')
    search_fields = ('title_ru', 'title_uz', 'course__title_ru')
    autocomplete_fields = ('course',)


@admin.register(Lesson, site=bodysteel_admin_site)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title_ru', 'module', 'position', 'is_preview', 'is_published')
    list_filter = ('is_published', 'is_preview', 'module__course')
    search_fields = ('title_ru', 'title_uz', 'module__title_ru', 'module__course__title_ru')
    autocomplete_fields = ('module',)
    inlines = (LessonMaterialInline,)


@admin.register(LessonMaterial, site=bodysteel_admin_site)
class LessonMaterialAdmin(admin.ModelAdmin):
    change_list_template = 'admin/courses/lessonmaterial/change_list.html'
    list_display = ('title_ru', 'lesson', 'kind', 'is_downloadable', 'position')
    list_filter = ('kind', 'is_downloadable', 'lesson__module__course')
    search_fields = ('title_ru', 'title_uz', 'lesson__title_ru')
    autocomplete_fields = ('lesson',)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'upload-multiple/',
                self.admin_site.admin_view(self.upload_multiple_view),
                name='courses_lessonmaterial_upload_multiple',
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        context = extra_context or {}
        context['upload_multiple_url'] = reverse(
            '{}:courses_lessonmaterial_upload_multiple'.format(self.admin_site.name),
        )
        return super().changelist_view(request, extra_context=context)

    def upload_multiple_view(self, request):
        form = LessonMaterialUploadForm(request.POST or None, request.FILES or None)
        if request.method == 'POST' and form.is_valid():
            lesson = form.cleaned_data['lesson']
            files = form.cleaned_data['files']
            start_position = LessonMaterial.objects.filter(lesson=lesson).aggregate(
                maximum=Max('position'),
            )['maximum']
            position = (start_position or 0) + 1
            for uploaded in files:
                name = os.path.splitext(uploaded.name)[0].replace('_', ' ').replace('-', ' ').strip()
                title = name or 'Материал урока'
                mime_type, _ = mimetypes.guess_type(uploaded.name)
                media_type = mime_type.split('/', 1)[0] if mime_type else 'file'
                if media_type not in {'image', 'video', 'audio'}:
                    media_type = 'file'
                LessonMaterial.objects.create(
                    lesson=lesson,
                    title_ru=title[:255],
                    title_uz=title[:255],
                    kind=media_type,
                    file=uploaded,
                    is_downloadable=form.cleaned_data['is_downloadable'],
                    position=position,
                )
                position += 1
            self.message_user(
                request,
                'Загружено материалов: {}.'.format(len(files)),
                messages.SUCCESS,
            )
            return HttpResponseRedirect(
                reverse('{}:courses_lessonmaterial_changelist'.format(self.admin_site.name)),
            )

        context = {
            **self.admin_site.each_context(request),
            'title': 'Загрузить несколько материалов',
            'form': form,
            'opts': self.model._meta,
            'media': self.media,
            'changelist_url': reverse(
                '{}:courses_lessonmaterial_changelist'.format(self.admin_site.name),
            ),
        }
        return TemplateResponse(request, 'admin/courses/lessonmaterial/upload_multiple.html', context)


@admin.register(CoursePurchase, site=bodysteel_admin_site)
class CoursePurchaseAdmin(admin.ModelAdmin):
    list_display = ('course_title', 'user', 'amount_display', 'status', 'created_at', 'paid_at')
    list_filter = ('status', 'course', 'created_at')
    search_fields = ('course_title', 'user__username', 'user__phone', 'user__email')
    list_select_related = ('user', 'course')
    readonly_fields = ('user', 'course', 'course_title', 'amount', 'currency', 'idempotency_digest', 'request_fingerprint', 'created_at', 'paid_at')

    @admin.display(description='Сумма')
    def amount_display(self, obj):
        return format_uzs(obj.amount)


@admin.register(CourseAccess, site=bodysteel_admin_site)
class CourseAccessAdmin(admin.ModelAdmin):
    list_display = ('course', 'user', 'status', 'source', 'granted_at', 'expires_at')
    list_filter = ('status', 'source', 'course')
    search_fields = ('course__title_ru', 'user__username', 'user__phone', 'user__email')
    autocomplete_fields = ('user', 'course', 'purchase')


@admin.register(LessonProgress, site=bodysteel_admin_site)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('access', 'lesson', 'percent', 'completed_at', 'updated_at')
    list_filter = ('percent', 'completed_at')
    search_fields = ('access__user__username', 'lesson__title_ru')
    readonly_fields = ('updated_at',)
