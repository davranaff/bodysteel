from django.urls import path

from store import views

urlpatterns = [
    path('home/', views.HomaPageAPIView.as_view(), name='home'),
]
