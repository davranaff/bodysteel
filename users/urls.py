from django.urls import path
from users import views
from users.auth import views as auth_views
from users.orders import views as order_views
from users.profile import views as profile_views


urlpatterns = [
    path('me/', profile_views.MeView.as_view(), name='me'),
    path('signup/', auth_views.SignUpView.as_view(), name='signup'),
    path('signin/', auth_views.SignInView.as_view(), name='signin'),
    path('sigout/', profile_views.SignOutView.as_view(), name='signout'),
    path('favorites/', views.FavoriteApi.as_view(), name='favorites'),
    path('create_favorites/', views.CreateFavoritesView.as_view(), name='create_favorites'),
    path('create_baskets/', views.CreateBasketsView.as_view(), name='create_baskets'),

    path('phone_verification/', auth_views.PhoneVerificationView.as_view(), name='phone_verification'),
    path('basket/', views.BasketAPIView.as_view(), name='basket'),
    path('orders/', order_views.OrderAPIView.as_view(), name='histories'),
    path('reviews/', views.ReviewAPIView.as_view(), name='reviews'),
    path('coupons/', views.CouponAPIView.as_view(), name='coupons'),
]
