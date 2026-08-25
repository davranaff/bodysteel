from django.urls import path

from customer_telegram.webhook import customer_telegram_webhook


urlpatterns = [
    path('webhook/', customer_telegram_webhook, name='webhook'),
]
