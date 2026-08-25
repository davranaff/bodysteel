import mimetypes
import os

from django.http import FileResponse
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Course, CourseAccess, CoursePurchase, Lesson, LessonMaterial
from courses.serializers import (
    CourseAccessSerializer,
    CoursePublicSerializer,
    CoursePurchaseSerializer,
    CoursePurchaseHistorySerializer,
    EmptyInputSerializer,
    PrivateLessonSerializer,
    ProgressSerializer,
    PublicLessonSerializer,
    language_from_request,
)
from courses.services import PurchaseConflict, PurchaseUnavailable, create_purchase
from users.orders.errors import InvalidOrderIdempotencyKey
from users.orders.idempotency import parse_idempotency_key


def public_courses():
    return Course.objects.filter(status=Course.PUBLISHED).prefetch_related(
        'modules__lessons__materials',
    )


def active_access(user, course):
    access = CourseAccess.objects.filter(
        user=user, course=course, status=CourseAccess.ACTIVE,
    ).select_related('course').first()
    if not access or not access.is_active():
        raise PermissionDenied('Course access is required')
    return access


class CourseViewSet(viewsets.ViewSet):
    def list(self, request):
        language = language_from_request(request)
        courses = public_courses()
        return Response({'data': CoursePublicSerializer(
            courses, many=True, context={'language': language},
        ).data})

    def retrieve(self, request, slug):
        course = get_object_or_404(public_courses(), slug=slug)
        return Response({'data': CoursePublicSerializer(
            course, context={'language': language_from_request(request)},
        ).data})


class CoursePurchaseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        serializer = EmptyInputSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            key = parse_idempotency_key(request.headers.get('Idempotency-Key'))
        except InvalidOrderIdempotencyKey:
            return Response({'detail': 'Idempotency-Key is invalid'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            purchase, payment, replayed = create_purchase(request.user, slug, key)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        except PurchaseUnavailable:
            return Response({'detail': 'Course is unavailable'}, status=status.HTTP_409_CONFLICT)
        except PurchaseConflict:
            return Response({'detail': 'Idempotency key conflict'}, status=status.HTTP_409_CONFLICT)
        response = Response({'data': CoursePurchaseSerializer(purchase).data}, status=status.HTTP_201_CREATED)
        if replayed:
            response['Idempotency-Replayed'] = 'true'
        return response


class MyCoursesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        access = CourseAccess.objects.filter(user=request.user).select_related('course').order_by('-granted_at')
        return Response({'data': CourseAccessSerializer(
            access, many=True, context={'language': language_from_request(request)},
        ).data})


class CoursePurchasesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        access_queryset = CourseAccess.objects.filter(user=request.user).order_by('-granted_at')
        purchases = CoursePurchase.objects.filter(user=request.user).select_related(
            'course',
        ).prefetch_related(
            'payments',
            Prefetch('course__access_grants', queryset=access_queryset, to_attr='account_accesses'),
        ).order_by('-created_at')
        return Response({'data': CoursePurchaseHistorySerializer(
            purchases,
            many=True,
            context={
                'language': language_from_request(request),
                'user': request.user,
            },
        ).data})


class CourseDetailForUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        course = get_object_or_404(Course.objects.prefetch_related('modules__lessons__materials'), slug=slug)
        access = active_access(request.user, course)
        language = language_from_request(request)
        progress_by_lesson = dict(access.progress.filter(
            lesson__module__course=course,
        ).values_list('lesson_id', 'percent'))
        payload = CoursePublicSerializer(course, context={'language': language}).data
        payload['access'] = CourseAccessSerializer(access, context={'language': language}).data
        payload['modules'] = [
            {
                'id': module.pk,
                'title': getattr(module, 'title_{}'.format(language)),
                'description': getattr(module, 'description_{}'.format(language)),
                'position': module.position,
                'lessons': PrivateLessonSerializer(
                    module.lessons.filter(is_published=True), many=True,
                    context={'language': language, 'progress_by_lesson': progress_by_lesson},
                ).data,
            }
            for module in course.modules.filter(is_published=True)
        ]
        return Response({'data': payload})


class CourseLessonAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        lesson = get_object_or_404(Lesson.objects.select_related('module__course').prefetch_related('materials'), pk=pk)
        access = active_access(request.user, lesson.module.course)
        return Response({'data': PrivateLessonSerializer(
            lesson,
            context={
                'language': language_from_request(request),
                'progress_by_lesson': dict(access.progress.filter(
                    lesson=lesson,
                ).values_list('lesson_id', 'percent')),
            },
        ).data})


class CourseProgressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        lesson = get_object_or_404(Lesson.objects.select_related('module__course'), pk=pk)
        access = active_access(request.user, lesson.module.course)
        serializer = ProgressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        percent = serializer.validated_data['percent']
        progress, _ = access.progress.update_or_create(
            lesson=lesson,
            defaults={
                'percent': percent,
                'completed_at': timezone.now() if percent == 100 else None,
            },
        )
        return Response({'data': {'lesson': lesson.pk, 'percent': progress.percent}})


class _ProtectedFileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def stream(self, request, lesson, field, filename):
        active_access(request.user, lesson.module.course)
        if not field:
            return Response({'detail': 'Material not found'}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(field.open('rb'), as_attachment=True, filename=filename)


class DownloadLessonMaterialAPIView(_ProtectedFileAPIView):
    def get(self, request, pk):
        material = get_object_or_404(
            LessonMaterial.objects.select_related('lesson__module__course'), pk=pk,
        )
        active_access(request.user, material.lesson.module.course)
        if not material.file:
            return Response({'detail': 'Material not found'}, status=status.HTTP_404_NOT_FOUND)
        content_type, _ = mimetypes.guess_type(material.file.name)
        return FileResponse(
            material.file.open('rb'),
            as_attachment=request.query_params.get('download') == '1',
            filename=os.path.basename(material.file.name),
            content_type=content_type or 'application/octet-stream',
        )
