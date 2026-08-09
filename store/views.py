"""Backward-compatible public facade for store HTTP adapters."""

from store.catalog.views import CategoryViewSet, ProductViewSet
from store.content.views import (
    AboutAPIView,
    BlogViewSet,
    BrandAPIView,
    DeliveryAndPaymentsAPIView,
    HomePageAPIView,
    SetOfProductViewSet,
)
from store.locations.views import FilialViewSet

# Keep the historical misspelling importable while new code uses the corrected name.
HomaPageAPIView = HomePageAPIView

__all__ = (
    'AboutAPIView',
    'BlogViewSet',
    'BrandAPIView',
    'CategoryViewSet',
    'DeliveryAndPaymentsAPIView',
    'FilialViewSet',
    'HomaPageAPIView',
    'HomePageAPIView',
    'ProductViewSet',
    'SetOfProductViewSet',
)
