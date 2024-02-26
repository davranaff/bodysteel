from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include([
        path('store/', include(('store.urls', 'store'), namespace='store')),
        path('users/', include(('users.urls', 'users'), namespace='users')),
    ]))
]
