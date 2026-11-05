from django.urls import path

from payments.multicard.views import (
    MulticardCallbackAPIView,
    MulticardOrderPaymentAPIView,
    MulticardPaymentStatusAPIView,
    MulticardWebhookAPIView,
    PaymentMethodsAPIView,
)
from payments.views import PaymentManualCompleteAPIView, PaymentStatusAPIView, PaymentWebhookAPIView

urlpatterns = [
    path('methods/', PaymentMethodsAPIView.as_view(), name='payment-methods'),
    path('orders/<int:order_id>/multicard/', MulticardOrderPaymentAPIView.as_view(), name='multicard-order-payment'),
    path('multicard/status/<str:token>/', MulticardPaymentStatusAPIView.as_view(), name='multicard-status'),
    path('multicard/callback/', MulticardCallbackAPIView.as_view(), name='multicard-callback'),
    path('multicard/webhook/', MulticardWebhookAPIView.as_view(), name='multicard-webhook'),
    path('<int:pk>/', PaymentStatusAPIView.as_view(), name='payment-status'),
    path('<int:pk>/manual-complete/', PaymentManualCompleteAPIView.as_view(), name='payment-manual-complete'),
    path('webhooks/<slug:provider>/', PaymentWebhookAPIView.as_view(), name='payment-webhook'),
]
