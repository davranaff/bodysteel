from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from store.admin_site import bodysteel_admin_site

schema_view = get_schema_view(
    openapi.Info(
        title="Snippets API",
        default_version='v1',
        description="Test description",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@snippets.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('integration/v1/', include(('integration.urls', 'integration'), namespace='integration')),
    path('admin/', bodysteel_admin_site.urls),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/v1/', include([
        path('documentation/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
        path('store/', include(('store.urls', 'store'), namespace='store')),
        path('users/', include(('users.urls', 'users'), namespace='users')),
    ])),
    path('telegram/', include(('teleg.urls', 'teleg'), namespace='telegram')),
    path(
        'telegram/customer/',
        include(('customer_telegram.urls', 'customer_telegram'), namespace='customer_telegram'),
    ),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
