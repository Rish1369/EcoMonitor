# EcoMonitor API

## Setup

1. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and set variables.
4. Run migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
5. Start the server:
   ```bash
   python manage.py runserver
   ```

## API Testing with Curl

### 1. Register a user
```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "password": "testpassword123", "email": "test@example.com", "organization": "Acme Corp", "phone": "555-1234"}'
```

### 2. Log in (Get JWT Token)
```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "password": "testpassword123"}'
```
*Extract the `access` token from the response for the following requests.*

### 3. Create a task
```bash
curl -X POST http://127.0.0.1:8000/api/tasks/ \
     -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"title": "My first report", "task_type": "REPORT_PDF"}'
```

### 4. List tasks
```bash
curl -X GET http://127.0.0.1:8000/api/tasks/ \
     -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```

### 5. Patch a task's status manually
```bash
curl -X PATCH http://127.0.0.1:8000/api/tasks/<TASK_ID>/ \
     -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"status": "PROCESSING"}'
```

### 6. Delete a task
```bash
curl -X DELETE http://127.0.0.1:8000/api/tasks/<TASK_ID>/ \
     -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```
