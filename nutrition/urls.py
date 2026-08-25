from django.urls import path

from nutrition.views import DeliveryOptionsAPIView, NutritionProductViewSet, NutritionViewSet
from nutrition.quote_views import CheckoutQuoteAPIView

urlpatterns = [
    path('', NutritionViewSet.as_view({'get': 'list'}), name='nutrition'),
    path('<slug>/', NutritionProductViewSet.as_view({'get': 'retrieve'}), name='nutrition-detail'),
    path('delivery/options/', DeliveryOptionsAPIView.as_view(), name='delivery-options'),
    path('checkout/quote/', CheckoutQuoteAPIView.as_view(), name='checkout-quote'),
]
