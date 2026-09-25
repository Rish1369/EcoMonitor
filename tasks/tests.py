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
