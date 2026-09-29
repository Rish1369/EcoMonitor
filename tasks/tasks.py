import time
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import NotificationLog, Task, AuditLog
from .services import transition

logger = logging.getLogger(__name__)

@shared_task(bind=True, acks_late=True, max_retries=3, default_retry_delay=5)
def process_task(self, task_id):
    try:
        task = transition(task_id, "PROCESSING", source="CELERY")
    except ValueError as e:
        logger.warning(f"Task {task_id} skipped: {e}")
        return str(task_id)
    
    time.sleep(10)
    
    result = {"report_url": f"/reports/{task_id}.pdf", "pages": 12}
    task = transition(task_id, "COMPLETED", source="CELERY", result=result)
    
    channel_type = NotificationLog.Channel.EMAIL if task.task_type == 'EMAIL' else NotificationLog.Channel.PDF
    NotificationLog.objects.create(
        user=task.owner,
        task_uuid=task.id,
        channel=channel_type,
        message=f"Task '{task.title}' completed"
    )
    
    return str(task.id)


@shared_task
def purge_old_completed_tasks():
    """
    Delete COMPLETED tasks older than 24 hours.

    WHY we read IDs before deleting:
      Task rows are about to disappear, but AuditLog.task is SET_NULL on
      delete, so the FK becomes NULL automatically.  We collect the IDs first
      so we can write a final "PURGED" tombstone AuditLog for each task,
      keeping a forensic trail (task=None, task_uuid still intact).
    """
    cutoff = timezone.now() - timedelta(hours=24)

    # Collect metadata before deletion so we can write tombstones.
    stale_tasks = list(
        Task.objects.filter(status="COMPLETED", completed_at__lt=cutoff)
        .values("id", "status")
    )

    if not stale_tasks:
        logger.info("purge_old_completed_tasks: nothing to delete.")
        return 0

    # Bulk-delete; CASCADE / SET_NULL rules apply automatically.
    deleted, _ = Task.objects.filter(
        status="COMPLETED", completed_at__lt=cutoff
    ).delete()

    # Write tombstone AuditLog rows (task FK is NULL after deletion).
    tombstones = [
        AuditLog(
            task=None,           # Task is gone; FK goes NULL.
            task_uuid=t["id"],   # UUID preserved for forensics.
            from_status="COMPLETED",
            to_status="PURGED",
            changed_by=None,
            source=AuditLog.Source.BEAT,
        )
        for t in stale_tasks
    ]
    AuditLog.objects.bulk_create(tombstones)

    logger.info(
        "purge_old_completed_tasks: deleted=%d, tombstones written=%d",
        deleted, len(tombstones),
    )
    return deleted
