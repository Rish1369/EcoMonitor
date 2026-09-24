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
