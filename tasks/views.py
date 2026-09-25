from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Task, AuditLog, NotificationLog
from .serializers import TaskSerializer, AuditLogSerializer, NotificationLogSerializer
from .tasks import process_task
from .services import transition

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['get'])
    def audit(self, request, pk=None):
        task = self.get_object()
        logs = AuditLog.objects.filter(task_uuid=task.id).order_by('-created_at')
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        task = self.get_object()
        
        if task.status != "PENDING":
            return Response(
                {"detail": "Task is not in PENDING state."}, 
                status=status.HTTP_409_CONFLICT
            )
            
        transaction.on_commit(lambda: process_task.delay(str(task.id)))
        
        return Response(
            {"id": str(task.id), "status": "QUEUED"}, 
            status=status.HTTP_202_ACCEPTED
        )

class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationLog.objects.filter(user=self.request.user).order_by('-sent_at')
