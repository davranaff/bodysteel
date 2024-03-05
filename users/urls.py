from django.urls import path
from users import views


urlpatterns = [
    path('me/', views.Me.as_view(), name='me'),
    path('signup/', views.SignUp.as_view(), name='signup'),
    path('signin/', views.SignIn.as_view(), name='signin'),
    path('sigout/', views.SignOut.as_view(), name='signout'),
    path('favorites/', views.FavoriteApi.as_view(), name='favorites'),

    path('phone_verification/', views.PhoneVerification.as_view(), name='phone_verification'),
    path('basket/', views.BasketAPIView.as_view(), name='basket'),
]
