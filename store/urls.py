from django.urls import path

from store import views
from store.views import CategoryViewSet, FilialViewSet, ProductViewSet

urlpatterns = [
    path('home/', views.HomePageAPIView.as_view(), name='home'),

    path('about/', views.AboutAPIView.as_view(), name='menu'),

    path('blogs/', views.BlogViewSet.as_view({'get': 'list'}), name='blogs'),
    path('blogs/<slug>/', views.BlogViewSet.as_view({'get': 'retrieve'}), name='blog_detail'),

    path('set_of_products/', views.SetOfProductViewSet.as_view({'get': 'list'}), name='set_of_products'),
    path('set_of_products/<slug>/', views.SetOfProductViewSet.as_view({'get': 'retrieve'}), name='set_of_product_detail'),

    path('brands/', views.BrandAPIView.as_view(), name='brands'),

    path('delivery_and_payment/', views.DeliveryAndPaymentsAPIView.as_view(), name='delivery_and_payments'),

    path('filiales/', FilialViewSet.as_view({'get': 'list', 'post': 'create'}), name='filiales'),
    path('filiales/<int:pk>/', FilialViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy',
    }), name='filial_detail'),
    path('filiales/<int:pk>/photos/', FilialViewSet.as_view({'post': 'add_photos'}), name='filial_add_photos'),
    path('filiales/<int:pk>/photos/<int:photo_id>/',
         FilialViewSet.as_view({'delete': 'delete_photo'}), name='filial_delete_photo'),

    path('products/', ProductViewSet.as_view({'get': 'list'}), name='products'),
    path('products/<slug>/', ProductViewSet.as_view({'get': 'retrieve'}, name="product_detail")),

    path('categories/', CategoryViewSet.as_view({'get': 'list'}), name='categories'),
    path('categories/<slug>/', CategoryViewSet.as_view({'get': 'retrieve'}, name="category_detail"))
]
