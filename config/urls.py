from django.contrib import admin
from django.urls import path, include

from tasks.views import NotificationViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'api/notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/tasks/', include('tasks.urls')),
    path('', include(router.urls)),
]
