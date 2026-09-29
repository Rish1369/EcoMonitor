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
5. Start Redis (requires Docker):
   ```bash
   docker run -d --name eco-redis -p 6379:6379 redis:7
   ```
6. Start the server (Terminal 1) using ASGI:
   ```bash
   uvicorn config.asgi:application --reload --port 8000
   ```
   *Note: Local development now runs via uvicorn instead of `python manage.py runserver`. This is because we are using `async def` views for high-concurrency polling endpoints. The traditional `runserver` runs under WSGI and forces all async views into a synchronous thread pool, which completely defeats the performance benefits of asynchronous I/O. Using an ASGI server like Uvicorn allows our async views to run natively in the event loop, maximizing throughput while our sync API views automatically run safely in a thread pool.*
7. Start the Celery worker (Terminal 2):
   ```bash
   celery -A config worker -l info
   ```
8. Start the Celery Beat scheduler (Terminal 3):
   ```bash
   celery -A config beat -l info
   ```
   *Beat runs the periodic task schedule defined in `config/celery.py`. By default it purges stale COMPLETED tasks once per hour (`crontab(minute=0)`). To shorten the interval for testing, set `PURGE_INTERVAL_SECONDS=60` in your `.env` before starting Beat.*


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

---

## Postman demo

Two importable files live in the `postman/` folder:

| File | Purpose |
|------|---------|
| `EcoMonitor.postman_collection.json` | Requests, folders, auth, and test scripts |
| `EcoMonitor.local.postman_environment.json` | Environment variables (base_url, tokens, etc.) |

### Import into Postman

1. Open Postman → **File → Import** (or drag-and-drop).
2. Select **both** files from the `postman/` directory.
3. In the top-right environment dropdown select **EcoMonitor – Local**.

### Step 1 — Authenticate (run once)

Open folder **1 - Auth** in the sidebar.

1. Send **Register** → should return `201 Created`.  
   *(If you get 400, the user already exists — skip to Login.)*
2. Send **Login** → should return `200 OK`.  
   The Tests script automatically saves `access_token` and `refresh_token`
   into the environment. All subsequent requests inherit
   `Authorization: Bearer {{access_token}}` via the collection-level auth
   setting — no manual copy-paste needed.

### Step 2 — Run the full Task lifecycle (Collection Runner)

1. Right-click folder **2 - Task Lifecycle** → **Run folder**.
2. Set **Iterations** to `5` (fires 5 independent jobs).
3. Ensure **Delay** is set to at least `500 ms` so the server has breathing
   room between requests.
4. Click **Run EcoMonitor API**.

#### What each request does

| # | Request | What to expect |
|---|---------|---------------|
| 1 | **Create Task** | `201 Created`; Tests script saves `current_task_id` and resets `poll_count=0`. |
| 2 | **Run Task** | `202 Accepted`; Celery worker picks up the job in the background. |
| 3 | **Poll Status** | `200 OK`; Tests script checks `status`. If `COMPLETED` → passes and moves on. If still `PROCESSING` → re-runs itself (up to 15 times). |

> **Note**: The Celery worker simulates work with `time.sleep(10)`, so each
> task takes ~10 seconds. With 5 iterations the Runner may take up to ~50 s.

#### What success looks like in the Runner result panel

```
Iteration 1
  ✅ Create Task        → 201  |  Created task: 3f8a...
  ✅ Run Task           → 202  |  Task queued
  ✅ Poll Status (×3)   → 200  |  Still PROCESSING (attempt 1, 2) … Task COMPLETED
Iteration 2 … (same pattern)
…
Iteration 5
  ✅ Create Task        → 201
  ✅ Run Task           → 202
  ✅ Poll Status (×N)   → 200  |  Task COMPLETED
```

All tests green, zero failures = everything is working end to end.

### Manual purge testing

```bash
# 1. Seed one stale and one fresh task
python manage.py purge_test_data

# 2. Open the shell and trigger the purge directly (no worker needed)
python manage.py shell
>>> from tasks.tasks import purge_old_completed_tasks
>>> purge_old_completed_tasks()   # Returns the number of deleted tasks (should be 1)
1

# 3. Verify
>>> from tasks.models import Task, AuditLog
>>> Task.objects.filter(title__startswith="[purge-test]").values("title", "status")
# Only the fresh task survives
>>> AuditLog.objects.filter(to_status="PURGED").values("task_uuid", "from_status")
# Tombstone AuditLog row — task=None but task_uuid intact
```
