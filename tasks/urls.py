from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet
from .async_views import task_status

router = DefaultRouter()
router.register(r'', TaskViewSet, basename='task')

urlpatterns = [
    path('status/', task_status, name='task-status'),
    path('', include(router.urls)),
]
