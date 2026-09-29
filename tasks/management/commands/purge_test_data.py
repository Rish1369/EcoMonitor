"""
Management command: purge_test_data

Creates two COMPLETED tasks for manual purge testing:
  1. A "stale" task  — completed_at 25 hours ago  → will be purged.
  2. A "fresh" task  — completed_at  1 hour  ago  → will survive.

Usage
-----
# 1. Create the test data
python manage.py purge_test_data

# 2. Open the Django shell
python manage.py shell

# 3. Trigger the purge task synchronously (no worker needed)
from tasks.tasks import purge_old_completed_tasks
deleted = purge_old_completed_tasks()
print(f"Deleted: {deleted}")

# 4. Verify — stale should be gone, fresh should remain
from tasks.models import Task, AuditLog
print("Remaining tasks:", Task.objects.filter(title__startswith="[purge-test]").values("title", "status"))
print("Tombstones:", AuditLog.objects.filter(to_status="PURGED").values("task_uuid", "from_status"))
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from tasks.models import Task

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Create one stale COMPLETED task (25 h old) and one fresh one (1 h old) "
        "so you can manually test purge_old_completed_tasks via the Django shell."
    )

    def handle(self, *args, **options):
        # Reuse or create a dedicated test user so the command is idempotent.
        user, created = User.objects.get_or_create(
            username="purge_test_user",
            defaults={"email": "purge@example.com"},
        )
        if created:
            user.set_password("testpass123")
            user.save()
            self.stdout.write(f"  Created user: {user.username}")
        else:
            self.stdout.write(f"  Reusing user: {user.username}")

        now = timezone.now()

        # ------------------------------------------------------------------ #
        # Stale task — completed 25 hours ago, SHOULD be purged.              #
        # ------------------------------------------------------------------ #
        stale = Task.objects.create(
            owner=user,
            title="[purge-test] Stale Task (25 h old) — should be PURGED",
            task_type=Task.TaskType.REPORT_PDF,
            status=Task.Status.COMPLETED,
        )
        # We use .update() to bypass auto_now on updated_at and set completed_at
        # to a backdated value.  .save() would overwrite updated_at with now().
        Task.objects.filter(pk=stale.pk).update(
            completed_at=now - timedelta(hours=25)
        )
        stale.refresh_from_db()

        # ------------------------------------------------------------------ #
        # Fresh task — completed 1 hour ago, SHOULD survive.                  #
        # ------------------------------------------------------------------ #
        fresh = Task.objects.create(
            owner=user,
            title="[purge-test] Fresh Task (1 h old) — should SURVIVE",
            task_type=Task.TaskType.REPORT_PDF,
            status=Task.Status.COMPLETED,
        )
        Task.objects.filter(pk=fresh.pk).update(
            completed_at=now - timedelta(hours=1)
        )
        fresh.refresh_from_db()

        self.stdout.write(self.style.SUCCESS("\nTest data created:"))
        self.stdout.write(
            f"  STALE  id={stale.pk}  completed_at={stale.completed_at}"
        )
        self.stdout.write(
            f"  FRESH  id={fresh.pk}  completed_at={fresh.completed_at}"
        )
        self.stdout.write(
            "\nNow open the Django shell and run:\n"
            "  from tasks.tasks import purge_old_completed_tasks\n"
            "  purge_old_completed_tasks()   # call directly (no worker)\n"
            "  # or via Celery (worker must be running):\n"
            "  purge_old_completed_tasks.delay()\n"
        )
