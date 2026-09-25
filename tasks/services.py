from django.utils import timezone
from django.db import transaction
from .models import Task, AuditLog

ALLOWED = {"PENDING": {"PROCESSING"}, "PROCESSING": {"COMPLETED"}}

@transaction.atomic
def transition(task_id, new_status, *, source, user=None, result=None):
    task = Task.objects.select_for_update().get(pk=task_id)
    if new_status not in ALLOWED.get(task.status, set()):
        raise ValueError(f"Illegal transition {task.status} -> {new_status}")
    old = task.status
    task.status = new_status
    now = timezone.now()
    if new_status == "PROCESSING":
        task.started_at = now
    if new_status == "COMPLETED":
        task.completed_at = now
        if result:
            task.result_data = result
    task.save()
    AuditLog.objects.create(
        task=task,
        task_uuid=task.id,
        from_status=old,
        to_status=new_status,
        changed_by=user,
        source=source
    )
    return task
