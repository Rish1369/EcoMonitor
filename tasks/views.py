from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Task
from .serializers import TaskSerializer
from .tasks import process_task

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

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
