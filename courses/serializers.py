import mimetypes
import os

from rest_framework import serializers

from courses.models import Course, CourseAccess, CourseModule, CoursePurchase, Lesson, LessonMaterial


def language_from_request(request):
    value = request.headers.get('Accept-Language', 'ru').lower()
    return 'uz' if value.startswith('uz') else 'ru'


def localized(instance, field, language):
    return getattr(instance, '{}_{}'.format(field, language))


def media_path(field):
    return field.url if field and field.name else None


def material_media_type(instance):
    value = (instance.kind or '').lower()
    if value in {'image', 'video', 'audio'}:
        return value
    name = instance.file.name if instance.file else instance.external_url
    mime_type, _ = mimetypes.guess_type(name or '')
    if mime_type and mime_type.split('/', 1)[0] in {'image', 'video', 'audio'}:
        return mime_type.split('/', 1)[0]
    return 'file'


class PublicLessonSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    media_types = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ('id', 'title', 'image', 'media_types', 'duration_minutes', 'position', 'is_preview')

    def get_title(self, instance):
        return localized(instance, 'title', self.context.get('language', 'ru'))

    def get_image(self, instance):
        return media_path(instance.image)

    def get_media_types(self, instance):
        values = ['image'] if instance.image else []
        values.extend(material_media_type(material) for material in instance.materials.all())
        unique = list(dict.fromkeys(values))
        if not unique:
            return ['text']
        if 'video' in unique and len(unique) > 1:
            return ['mixed']
        return unique


class PublicModuleSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    lessons = serializers.SerializerMethodField()

    class Meta:
        model = CourseModule
        fields = ('id', 'title', 'description', 'position', 'lessons')

    def get_title(self, instance):
        return localized(instance, 'title', self.context.get('language', 'ru'))

    def get_description(self, instance):
        return localized(instance, 'description', self.context.get('language', 'ru'))

    def get_lessons(self, instance):
        lessons = instance.lessons.filter(is_published=True)
        return PublicLessonSerializer(
            lessons, many=True, context=self.context,
        ).data


class CoursePublicSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    modules = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ('id', 'slug', 'title', 'summary', 'description', 'cover', 'price', 'duration', 'modules')

    def _language(self):
        return self.context.get('language', 'ru')

    def get_title(self, instance):
        return localized(instance, 'title', self._language())

    def get_summary(self, instance):
        return localized(instance, 'summary', self._language())

    def get_description(self, instance):
        return localized(instance, 'description', self._language())

    def get_cover(self, instance):
        return media_path(instance.cover)

    def get_price(self, instance):
        return {'amount': instance.price, 'currency': instance.currency}

    def get_duration(self, instance):
        return {'days': instance.duration_days, 'minutes': instance.estimated_minutes}

    def get_modules(self, instance):
        modules = instance.modules.filter(is_published=True)
        return PublicModuleSerializer(modules, many=True, context=self.context).data


class PrivateLessonSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    materials = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ('id', 'title', 'text', 'image', 'duration_minutes', 'position', 'materials', 'progress')

    def _language(self):
        return self.context.get('language', 'ru')

    def get_title(self, instance):
        return localized(instance, 'title', self._language())

    def get_text(self, instance):
        return localized(instance, 'text', self._language())

    def get_image(self, instance):
        return media_path(instance.image)

    def get_materials(self, instance):
        return MaterialSerializer(instance.materials.all(), many=True, context=self.context).data

    def get_progress(self, instance):
        progress_by_lesson = self.context.get('progress_by_lesson', {})
        value = progress_by_lesson.get(instance.pk, 0)
        return value if isinstance(value, int) and 0 <= value <= 100 else 0


class MaterialSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    media_type = serializers.SerializerMethodField()

    class Meta:
        model = LessonMaterial
        fields = ('id', 'title', 'kind', 'media_type', 'file_name', 'url', 'is_downloadable', 'position')

    def get_title(self, instance):
        return localized(instance, 'title', self.context.get('language', 'ru'))

    def get_url(self, instance):
        if instance.file:
            return '/api/v1/courses/materials/{}/download/'.format(instance.pk)
        return instance.external_url if instance.external_url.startswith('https://') else None

    def get_file_name(self, instance):
        if instance.file:
            return os.path.basename(instance.file.name)
        return ''

    def get_media_type(self, instance):
        return material_media_type(instance)


class CourseAccessSerializer(serializers.ModelSerializer):
    course = CoursePublicSerializer(read_only=True)

    class Meta:
        model = CourseAccess
        fields = ('id', 'course', 'source', 'status', 'granted_at', 'expires_at')


class CoursePurchaseSerializer(serializers.ModelSerializer):
    payment = serializers.SerializerMethodField()

    class Meta:
        model = CoursePurchase
        fields = ('id', 'course', 'course_title', 'amount', 'currency', 'status', 'created_at', 'paid_at', 'payment')

    def get_payment(self, instance):
        payment = instance.payments.order_by('-created_at').first()
        if not payment:
            return None
        return {
            'id': payment.pk,
            'provider': payment.provider,
            'status': payment.status,
            'amount': payment.amount,
            'currency': payment.currency,
        }


class CoursePurchaseHistorySerializer(serializers.ModelSerializer):
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    course_title = serializers.SerializerMethodField()
    course_cover = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    access = serializers.SerializerMethodField()

    class Meta:
        model = CoursePurchase
        fields = (
            'id', 'course', 'course_slug', 'course_title', 'course_cover',
            'amount', 'currency', 'status', 'created_at', 'paid_at',
            'payment', 'access',
        )

    def _language(self):
        return self.context.get('language', 'ru')

    def get_course_title(self, instance):
        return localized(instance.course, 'title', self._language())

    def get_course_cover(self, instance):
        return media_path(instance.course.cover)

    def get_payment(self, instance):
        payment = instance.payments.order_by('-created_at').first()
        if not payment:
            return None
        return {
            'id': payment.pk,
            'provider': payment.provider,
            'status': payment.status,
            'amount': payment.amount,
            'currency': payment.currency,
        }

    def get_access(self, instance):
        accesses = getattr(instance.course, 'account_accesses', None)
        if accesses is None:
            user = self.context.get('user')
            accesses = instance.course.access_grants.filter(user=user).order_by('-granted_at') if user else []
        access = accesses[0] if accesses else None
        if not access:
            return None
        return {
            'id': access.pk,
            'status': access.status,
            'source': access.source,
            'granted_at': access.granted_at,
            'expires_at': access.expires_at,
        }


class EmptyInputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or data:
            raise serializers.ValidationError({'detail': 'Request body must be empty'})
        return {}


class ProgressSerializer(serializers.Serializer):
    percent = serializers.IntegerField(min_value=0, max_value=100)
