from django.urls import path

from courses.views import (
    CourseDetailForUserAPIView,
    CourseLessonAPIView,
    CourseProgressAPIView,
    CoursePurchaseAPIView,
    CoursePurchasesAPIView,
    CourseViewSet,
    DownloadLessonMaterialAPIView,
    MyCoursesAPIView,
)

urlpatterns = [
    path('', CourseViewSet.as_view({'get': 'list'}), name='course-list'),
    path('me/', MyCoursesAPIView.as_view(), name='my-courses'),
    path('me/<slug:slug>/', CourseDetailForUserAPIView.as_view(), name='my-course-detail'),
    path('me/lessons/<int:pk>/', CourseLessonAPIView.as_view(), name='my-lesson'),
    path('me/lessons/<int:pk>/progress/', CourseProgressAPIView.as_view(), name='my-lesson-progress'),
    path('materials/<int:pk>/download/', DownloadLessonMaterialAPIView.as_view(), name='material-download'),
    path('purchases/', CoursePurchasesAPIView.as_view(), name='course-purchases'),
    path('<slug:slug>/', CourseViewSet.as_view({'get': 'retrieve'}), name='course-detail'),
    path('<slug:slug>/purchases/', CoursePurchaseAPIView.as_view(), name='course-purchase'),
]
