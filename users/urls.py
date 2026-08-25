from django.urls import path
from users import views
from users.auth import views as auth_views
from users.orders import views as order_views
from users.profile import views as profile_views
from customer_telegram import api_views as customer_telegram_views


urlpatterns = [
    path('me/', profile_views.MeView.as_view(), name='me'),
    path('delete/', profile_views.DeleteAccountView.as_view(), name='delete-account'),
    path('password/change/', profile_views.ChangePasswordView.as_view(), name='password-change'),
    path('sessions/', profile_views.SessionsView.as_view(), name='sessions'),
    path('sessions/revoke-all/', profile_views.RevokeAllSessionsView.as_view(), name='sessions-revoke-all'),
    path('email/change/start/', profile_views.EmailChangeStartView.as_view(), name='email-change-start'),
    path('phone/change/start/', profile_views.PhoneChangeStartView.as_view(), name='phone-change-start'),
    path('contact/verify/', profile_views.ContactVerificationCompleteView.as_view(), name='contact-verify'),
    path('signup/', auth_views.SignUpView.as_view(), name='signup'),
    path('signin/', auth_views.SignInView.as_view(), name='signin'),
    path('sigout/', profile_views.SignOutView.as_view(), name='signout'),
    path('signout/', profile_views.SignOutView.as_view(), name='signout-canonical'),
    path('favorites/', views.FavoriteApi.as_view(), name='favorites'),
    path('create_favorites/', views.CreateFavoritesView.as_view(), name='create_favorites'),
    path('create_baskets/', views.CreateBasketsView.as_view(), name='create_baskets'),

    path('phone_verification/', auth_views.PhoneVerificationView.as_view(), name='phone_verification'),
    path('password/forgot/', auth_views.PasswordResetRequestView.as_view(), name='password-forgot'),
    path('password/reset/', auth_views.PasswordResetCompleteView.as_view(), name='password-reset'),
    path('dev/otp/<uuid:challenge_id>/', auth_views.DevOtpView.as_view(), name='dev-otp'),
    path(
        'telegram/registration/start/',
        customer_telegram_views.TelegramRegistrationStartView.as_view(),
        name='telegram-registration-start',
    ),
    path(
        'telegram/password/forgot/',
        customer_telegram_views.TelegramPasswordResetStartView.as_view(),
        name='telegram-password-forgot',
    ),
    path(
        'telegram/account/', customer_telegram_views.TelegramAccountView.as_view(),
        name='telegram-account',
    ),
    path(
        'telegram/account/link/start/',
        customer_telegram_views.TelegramAccountLinkStartView.as_view(),
        name='telegram-account-link-start',
    ),
    path(
        'telegram/account/unlink/',
        customer_telegram_views.TelegramAccountUnlinkView.as_view(),
        name='telegram-account-unlink',
    ),
    path('basket/', views.BasketAPIView.as_view(), name='basket'),
    path('orders/', order_views.OrderAPIView.as_view(), name='histories'),
    path('reviews/', views.ReviewAPIView.as_view(), name='reviews'),
    path('coupons/', views.CouponAPIView.as_view(), name='coupons'),
]
