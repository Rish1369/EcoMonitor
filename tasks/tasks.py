import time
import logging
from celery import shared_task
from .models import NotificationLog
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
