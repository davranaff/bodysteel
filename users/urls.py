from django.urls import path
from users import views


urlpatterns = [
    path('me/', views.Me.as_view(), name='me'),
    path('signup/', views.SignUp.as_view(), name='signup'),
    path('sigin/', views.SignIn.as_view(), name='signin'),
    path('sigout/', views.SignOut.as_view(), name='signout'),
]
