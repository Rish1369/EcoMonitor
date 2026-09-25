from django.contrib import admin
from .models import Task, AuditLog, NotificationLog

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'task_type', 'status', 'owner', 'created_at', 'updated_at')
    list_filter = ('status', 'task_type')
    search_fields = ('title', 'owner__username')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_uuid', 'from_status', 'to_status', 'source', 'changed_by', 'created_at')
    list_filter = ('source', 'from_status', 'to_status')
    search_fields = ('task_uuid',)

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_uuid', 'user', 'channel', 'sent_at')
    list_filter = ('channel',)
    search_fields = ('task_uuid', 'user__username', 'message')
