from django.urls import path

from store import views
from store.views import ProductViewSet, CategoryViewSet

urlpatterns = [
    path('home/', views.HomaPageAPIView.as_view(), name='home'),

    path('about/', views.AboutAPIView.as_view(), name='menu'),

    path('blogs/', views.BlogViewSet.as_view({'get': 'list'}), name='blogs'),
    path('blogs/<pk>/', views.BlogViewSet.as_view({'get': 'retrieve'}), name='blog_detail'),

    path('set_of_products/', views.SetOfProductViewSet.as_view({'get': 'list'}), name='set_of_products'),
    path('set_of_products/<pk>/', views.SetOfProductViewSet.as_view({'get': 'retrieve'}), name='set_of_product_detail'),

    path('brands/', views.BrandAPIView.as_view(), name='brands'),

    path('delivery_and_payment/', views.DeliveryAndPaymentsAPIView.as_view(), name='delivery_and_payments'),

    path('filiales/', views.FilialAPIView.as_view(), name='filiales'),

    path('products/', ProductViewSet.as_view({'get': 'list'}), name='products'),
    path('products/<pk>/', ProductViewSet.as_view({'get': 'retrieve'}, name="product_detail")),

    path('categories/', CategoryViewSet.as_view({'get': 'list'}), name='categories'),
    path('categories/<pk>/', CategoryViewSet.as_view({'get': 'retrieve'}, name="category_detail"))
]
