from django.urls import path

from payments.views import PaymentManualCompleteAPIView, PaymentStatusAPIView, PaymentWebhookAPIView

urlpatterns = [
    path('<int:pk>/', PaymentStatusAPIView.as_view(), name='payment-status'),
    path('<int:pk>/manual-complete/', PaymentManualCompleteAPIView.as_view(), name='payment-manual-complete'),
    path('webhooks/<slug:provider>/', PaymentWebhookAPIView.as_view(), name='payment-webhook'),
]
