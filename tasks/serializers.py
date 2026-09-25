from rest_framework import serializers
from .models import Task, AuditLog

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        exclude = ('owner',)
        read_only_fields = ('id', 'status', 'result_data', 'created_at', 'updated_at', 'started_at', 'completed_at')

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'

from .models import NotificationLog

class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        exclude = ('user',)
