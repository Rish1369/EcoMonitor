from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import Task

User = get_user_model()

class TaskAPITests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='password123')
        self.user2 = User.objects.create_user(username='user2', password='password123')
        
        self.task1 = Task.objects.create(
            owner=self.user1,
            title='User 1 Task',
            task_type=Task.TaskType.REPORT_PDF
        )
        self.task2 = Task.objects.create(
            owner=self.user2,
            title='User 2 Task',
            task_type=Task.TaskType.EMAIL
        )
        self.url = '/api/tasks/'

    def test_unauthenticated_requests_get_401(self):
        """Unauthenticated requests get 401"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        response = self.client.post(self.url, {'title': 'New Task', 'task_type': 'EMAIL'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_only_see_their_own_tasks(self):
        """User can only see their own tasks"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], str(self.task1.id))
        self.assertEqual(data[0]['title'], 'User 1 Task')

    def test_task_creation_sets_pending_by_default(self):
        """Task creation sets PENDING by default"""
        self.client.force_authenticate(user=self.user1)
        payload = {
            'title': 'New Report Task',
            'task_type': 'REPORT_PDF'
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        data = response.json()
        self.assertEqual(data['status'], 'PENDING')
        
        # Verify in database
        task = Task.objects.get(id=data['id'])
        self.assertEqual(task.status, Task.Status.PENDING)
        self.assertEqual(task.owner, self.user1)

from .services import transition
from .models import AuditLog, NotificationLog

class TransitionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='123')
        self.task = Task.objects.create(
            owner=self.user,
            title='Test Task',
            task_type=Task.TaskType.EMAIL
        )
        self.url = f'/api/tasks/{self.task.id}/run/'

    def test_illegal_transition_raises_value_error(self):
        """Illegal transition raises ValueError"""
        with self.assertRaises(ValueError):
            transition(self.task.id, "COMPLETED", source="CELERY")

    def test_running_transition_twice_idempotent(self):
        """Running transition() twice on the same completed task doesn't create duplicate side effects"""
        transition(self.task.id, "PROCESSING", source="CELERY")
        transition(self.task.id, "COMPLETED", source="CELERY")
        
        # It's completed now. Running it again should raise ValueError
        with self.assertRaises(ValueError):
            transition(self.task.id, "COMPLETED", source="CELERY")

    def test_audit_log_has_exactly_two_rows(self):
        """AuditLog has exactly 2 rows after a normal run"""
        transition(self.task.id, "PROCESSING", source="CELERY")
        transition(self.task.id, "COMPLETED", source="CELERY")
        
        logs = AuditLog.objects.filter(task_uuid=self.task.id).order_by('created_at')
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs[0].from_status, "PENDING")
        self.assertEqual(logs[0].to_status, "PROCESSING")
        self.assertEqual(logs[1].from_status, "PROCESSING")
        self.assertEqual(logs[1].to_status, "COMPLETED")

    def test_409_returned_when_rerunning_non_pending_task(self):
        """409 returned when re-running a non-PENDING task"""
        self.task.status = "PROCESSING"
        self.task.save()
        
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

class AsyncStatusViewTests(APITestCase):
    def setUp(self):
        self.userA = User.objects.create_user(username='userA', password='123')
        self.userB = User.objects.create_user(username='userB', password='123')
        
        self.tasksA = [
            Task.objects.create(owner=self.userA, title=f'Task A {i}', task_type=Task.TaskType.EMAIL)
            for i in range(3)
        ]
        self.taskB = Task.objects.create(owner=self.userB, title='Task B', task_type=Task.TaskType.EMAIL)
        
        # Get JWT token since async view uses jwt_required_async decorator
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken.for_user(self.userA)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_async_status_view_returns_only_owned_tasks(self):
        """Test hits /api/tasks/status/?ids=<all 4 ids>, and asserts only user A's 3 come back."""
        all_ids = [str(t.id) for t in self.tasksA] + [str(self.taskB.id)]
        ids_param = ",".join(all_ids)
        
        response = self.client.get(f'/api/tasks/status/?ids={ids_param}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["results"]), 3)
        
        returned_ids = {r["id"] for r in data["results"]}
        expected_ids = {str(t.id) for t in self.tasksA}
        self.assertEqual(returned_ids, expected_ids)


# ---------------------------------------------------------------------------
# Beat / purge tests
# ---------------------------------------------------------------------------

from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch
from .tasks import purge_old_completed_tasks


class PurgeTaskTests(APITestCase):
    """
    Tests for purge_old_completed_tasks.

    Design notes
    ------------
    • completed_at uses auto_now=False so we can back-date it directly via
      .update(), which bypasses model validation and auto_now fields.
    • We call the task function directly (no Celery worker needed) so tests
      run fast and deterministically.
    • The critical assertion is that AuditLog tombstones survive with
      task=None but task_uuid intact — this proves forensic history is
      preserved even after the Task row is gone.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="purge_user", password="pw")

    def _make_completed_task(self, title, hours_ago):
        """
        Create a COMPLETED Task whose completed_at is backdated by
        `hours_ago` hours.  We use .update() so auto_now doesn't
        overwrite our backdated timestamp.
        """
        task = Task.objects.create(
            owner=self.user,
            title=title,
            task_type=Task.TaskType.REPORT_PDF,
            status=Task.Status.COMPLETED,
        )
        backdated = timezone.now() - timedelta(hours=hours_ago)
        Task.objects.filter(pk=task.pk).update(completed_at=backdated)
        task.refresh_from_db()
        return task

    def test_stale_task_is_deleted(self):
        """A COMPLETED task whose completed_at is >24 h ago is purged."""
        stale = self._make_completed_task("Stale Task", hours_ago=25)
        result = purge_old_completed_tasks()
        self.assertEqual(result, 1)
        self.assertFalse(Task.objects.filter(pk=stale.pk).exists())

    def test_fresh_task_survives(self):
        """A COMPLETED task whose completed_at is <24 h ago is kept."""
        fresh = self._make_completed_task("Fresh Task", hours_ago=1)
        result = purge_old_completed_tasks()
        self.assertEqual(result, 0)
        self.assertTrue(Task.objects.filter(pk=fresh.pk).exists())

    def test_stale_deleted_fresh_survives_together(self):
        """
        When both a stale and a fresh task exist, only the stale one
        is deleted and only one tombstone is written.
        """
        stale = self._make_completed_task("Stale", hours_ago=25)
        fresh = self._make_completed_task("Fresh", hours_ago=1)

        result = purge_old_completed_tasks()

        self.assertEqual(result, 1)
        self.assertFalse(Task.objects.filter(pk=stale.pk).exists())
        self.assertTrue(Task.objects.filter(pk=fresh.pk).exists())

    def test_tombstone_auditlog_preserved_after_purge(self):
        """
        After purge, AuditLog rows for the deleted task must have:
          - task       = None   (FK set to NULL because Task is gone)
          - task_uuid  = <original UUID>   (forensic trail intact)
          - to_status  = "PURGED"
          - source     = "BEAT"
        """
        stale = self._make_completed_task("Stale For Tombstone", hours_ago=25)
        stale_uuid = stale.pk  # Capture before deletion.

        purge_old_completed_tasks()

        # The Task row itself must be gone.
        self.assertFalse(Task.objects.filter(pk=stale_uuid).exists())

        # The tombstone AuditLog must exist and have the correct shape.
        tombstone = AuditLog.objects.get(
            task_uuid=stale_uuid, to_status="PURGED"
        )
        self.assertIsNone(tombstone.task)          # FK is NULL — task is gone.
        self.assertEqual(tombstone.task_uuid, stale_uuid)  # UUID intact.
        self.assertEqual(tombstone.from_status, "COMPLETED")
        self.assertEqual(tombstone.source, AuditLog.Source.BEAT)

    def test_pending_task_not_touched_by_purge(self):
        """Purge must never delete a PENDING task regardless of age."""
        old_pending = Task.objects.create(
            owner=self.user,
            title="Old Pending",
            task_type=Task.TaskType.EMAIL,
            status=Task.Status.PENDING,
        )
        # Back-date updated_at to look old (doesn't matter for purge filter,
        # but makes the test intent explicit).
        Task.objects.filter(pk=old_pending.pk).update(
            completed_at=timezone.now() - timedelta(hours=48)
        )
        result = purge_old_completed_tasks()
        self.assertEqual(result, 0)
        self.assertTrue(Task.objects.filter(pk=old_pending.pk).exists())

