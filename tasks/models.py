import uuid
from django.db import models
from django.conf import settings

class Task(models.Model):
    class TaskType(models.TextChoices):
        REPORT_PDF = 'REPORT_PDF', 'Report PDF'
        EMAIL = 'EMAIL', 'Email'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    task_type = models.CharField(max_length=50, choices=TaskType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    result_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class AuditLog(models.Model):
    class Source(models.TextChoices):
        API = 'API', 'API'
        CELERY = 'CELERY', 'Celery'
        BEAT = 'BEAT', 'Beat'

    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    task_uuid = models.UUIDField(db_index=True)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    source = models.CharField(max_length=20, choices=Source.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Task {self.task_uuid}: {self.from_status} -> {self.to_status}"

class NotificationLog(models.Model):
    class Channel(models.TextChoices):
        EMAIL = 'EMAIL', 'Email'
        PDF = 'PDF', 'PDF'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    task_uuid = models.UUIDField(db_index=True)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user}: {self.message}"
