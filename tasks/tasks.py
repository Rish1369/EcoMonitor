import time
from celery import shared_task
from django.utils import timezone
from .models import Task

@shared_task
def process_task(task_id):
    task = Task.objects.get(pk=task_id)
    task.status = "PROCESSING"
    task.started_at = timezone.now()
    task.save()
    
    time.sleep(10)
    
    task.status = "COMPLETED"
    task.completed_at = timezone.now()
    task.result_data = {"report_url": f"/reports/{task_id}.pdf", "pages": 12}
    task.save()
    
    return str(task.id)
