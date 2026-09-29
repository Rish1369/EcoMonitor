import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ---------------------------------------------------------------------------
# Celery Beat schedule
# ---------------------------------------------------------------------------
# PURGE_INTERVAL_SECONDS lets you shrink the interval for local testing
# without touching code.  Example: export PURGE_INTERVAL_SECONDS=60
# leaves the beat running every minute so you can verify purges quickly.
# When the variable is absent we fall back to a safe hourly crontab.

_purge_seconds = os.environ.get("PURGE_INTERVAL_SECONDS")

if _purge_seconds:
    # timedelta-based schedule: runs every N seconds.
    # Useful for development — set PURGE_INTERVAL_SECONDS=60 to see a purge
    # happen once a minute instead of waiting an hour.
    from datetime import timedelta
    _purge_schedule = timedelta(seconds=int(_purge_seconds))
else:
    # Production default: top of every hour (00:00, 01:00, 02:00 …).
    _purge_schedule = crontab(minute=0)

app.conf.beat_schedule = {
    "purge-old-completed-tasks": {
        "task": "tasks.tasks.purge_old_completed_tasks",
        "schedule": _purge_schedule,
        # Options forwarded to the Celery worker that picks up this task.
        "options": {"expires": 3600},  # Discard if not consumed within 1 h.
    },
}
