from django.urls import path

from integration.catalog.views import InventoryView, ProductView, ProductsView
from integration.carts.views import CartRestoreView, CartsView
from integration.regos.views import RegosToServerView


app_name = 'integration'

urlpatterns = [
    path('products', ProductsView.as_view(), name='products'),
    path('products/<str:product_id>', ProductView.as_view(), name='product'),
    path('inventory', InventoryView.as_view(), name='inventory'),
    path('carts', CartsView.as_view(), name='carts'),
    path('cart-restores', CartRestoreView.as_view(), name='cart_restore'),
    path('regos/to-server', RegosToServerView.as_view(), name='regos_to_server'),
]
