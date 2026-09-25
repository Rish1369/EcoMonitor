# Django & DRF Interview Revision Notes

This document contains a structured breakdown of core Django and Django REST Framework (DRF) concepts, based on the `EcoMonitor` project architecture.

---

## 1. Project Configuration (`settings.py`)

### `BASE_DIR` & Pathlib
```python
BASE_DIR = Path(__file__).resolve().parent.parent
```
* **Concept:** Dynamic Pathing.
* **Explanation:** Django uses `BASE_DIR` as the "home base" to locate the database, static files, and templates. Using `Path(__file__)` ensures the app works on any operating system (Windows/Mac/Linux) without hardcoding absolute paths.

### `SECRET_KEY` & `DEBUG`
```python
SECRET_KEY = os.getenv('SECRET_KEY', 'default-insecure-key')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
```
* **Concept:** Security & Environment Variables.
* **Explanation:** The `SECRET_KEY` handles cryptographic signing (like session cookies and password reset tokens). `DEBUG=True` shows detailed crash pages. Both must be managed via environment variables (like a `.env` file) so sensitive data isn't exposed in GitHub or left active in a production environment.

---

## 2. Object-Oriented Programming: The `self` Keyword

* **Concept:** Instance references in Python OOP.
* **Explanation:** When you write `def __str__(self):` inside a Django model (like `Task`), `self` refers to the **specific, individual instance** of the object being acted upon. 
* **Analogy:** If the class is the blueprint, `self` is the specific house built from that blueprint. It allows the function to access data specific to that instance (e.g., `self.title` gives the title of *that specific task*).

---

## 3. Serializers (`serializers.py`)

### The `Meta` Class (The Bouncer)
```python
class Meta:
    model = User
    fields = ('username', 'password', 'email', 'organization', 'phone')
```
* **Concept:** Data Validation & Whitelisting.
* **Explanation:** The `Meta` class tells the serializer which database model to map to. The `fields` tuple acts as a strict whitelist. If a malicious user tries to send an extra JSON field (like `"is_superuser": true`), the serializer ignores it entirely.

### Overriding `create()`
```python
def create(self, validated_data):
    user = User.objects.create_user(
        username=validated_data['username'],
        password=validated_data['password']
    )
    return user
```
* **Concept:** Intercepting Model Creation & Password Hashing.
* **Explanation:** Normally, a `ModelSerializer` saves data exactly as it receives it. We override `create()` to intercept the `password` field and pass it through Django's `create_user()` method, which safely **hashes** the password before saving it to the database.

---

## 4. Views & Class-Based Magic (`views.py`)

### `CreateAPIView` (Users App)
* **Concept:** Generic Views & Mixins.
* **Explanation:** By inheriting from `CreateAPIView`, DRF handles all the underlying logic of a POST request. It automatically calls `self.create()` (inherited from `CreateModelMixin`). 
* **The Flow:** DRF takes the incoming JSON, passes it to the `serializer_class`, validates it, and if valid, saves it to the `queryset` database table.

### `ModelViewSet` (Tasks App)
* **Concept:** ViewSets & CRUD Automation.
* **Explanation:** Inheriting from `ModelViewSet` automatically generates the logic for all 5 standard REST endpoints (List, Retrieve, Create, Update, Delete) in just a few lines of code.

### Securing the View (`get_queryset` & `perform_create`)
```python
def get_queryset(self):
    return Task.objects.filter(owner=self.request.user)

def perform_create(self, serializer):
    serializer.save(owner=self.request.user)
```
* **Concept:** Request-level Filtering.
* **Explanation:** Overriding `get_queryset()` ensures a user can only query the database for tasks *they* own. Overriding `perform_create()` prevents users from manually assigning the `owner` field in their JSON; the server intercepts it and forces `owner=request.user`.

---

## 5. URL Routing & Aliases (`urls.py`)

### The `name` Parameter
```python
path('register/', RegisterView.as_view(), name='register')
```
* **Concept:** URL Reversing.
* **Explanation:** The `name='register'` parameter assigns a permanent alias to a URL. By using Django's `reverse('register')` function in tests or templates, you can dynamically generate the URL. If the actual path changes later (e.g., to `/signup/`), you don't have to update hardcoded strings across your codebase.

### DRF Routers
```python
router = DefaultRouter()
router.register(r'', TaskViewSet, basename='task')
```
* **Concept:** Automatic URL Generation.
* **Explanation:** When you register a `ModelViewSet` with a router, DRF automatically maps and generates the 5 standard API URLs (GET, POST, PATCH, DELETE) behind the scenes, saving you from writing them out manually.

---

## 6. JWT Authentication (`djangorestframework-simplejwt`)

### How Login Works
* **Concept:** Stateless Authentication.
* **Explanation:** There is no standard "Login View" returning an HTML session cookie. Instead, a user sends a POST request with their username/password to the `/token/` endpoint. The server verifies the credentials and returns two cryptographic tokens: an `access` token (short lifespan, ~5 mins) and a `refresh` token (longer lifespan).

### How DRF Validates the Token
* **Concept:** The Authentication Pipeline.
* **Explanation:** When a user requests a protected route with `Authorization: Bearer <token>`:
  1. The global **`JWTAuthentication`** class (set in `settings.py`) catches the request.
  2. It mathematically verifies the cryptographic signature of the token and checks expiration.
  3. It extracts the `user_id` from the token, finds the user in the database, and attaches them to `request.user`.
  4. Finally, the view's **`IsAuthenticated`** permission class simply checks if `request.user` successfully exists.

---

## 7. Celery & Background Processing

### The Initialization Hook (`config/__init__.py`)
```python
from .celery import app as celery_app
__all__ = ('celery_app',)
```
* **Concept:** Forcing App Initialization.
* **Explanation:** When Django starts, it imports the `config` module, triggering this `__init__.py` file immediately. Importing `celery_app` forces Python to evaluate `config/celery.py`, officially turning on the Celery application in memory. This is mandatory so decorators like `@shared_task` (which are imported generically from the celery library) can find an active Celery instance to bind to.
* **The `__all__` variable:** This explicitly defines the public API of the module. It strictly tells Python: "If a developer does `from config import *`, ONLY export `celery_app`." It prevents accidentally leaking or exposing other internal variables.

### The Custom `@action` Decorator (`tasks/views.py`)
```python
@action(detail=True, methods=['post'])
def run(self, request, pk=None):
```
* **Concept:** Custom ViewSet Endpoints.
* **Explanation:** While `ModelViewSet` automatically generates standard CRUD routes, decorators like `@action` allow you to bolt on custom operations (like "Run Task").
* **`detail=True`:** Tells the DRF Router this action applies to a single database row, forcing it to generate a URL that requires an ID (e.g., `/api/tasks/<pk>/run/`).
* **Retrieving the Task (`self.get_object()`):** Because `detail=True` forces an ID in the URL, DRF automatically extracts that ID and makes it available. Calling `self.get_object()` automatically queries the database using that ID, verifies the user owns it (using our `get_queryset` rules), and returns the specific `Task` object.

### Dispatching Tasks Safely

```python
transaction.on_commit(lambda: process_task.delay(str(task.id)))
```

- **`.delay()`**: Sends the Celery task to the configured **message broker** (commonly Redis or RabbitMQ) instead of executing it synchronously. The broker is determined by `CELERY_BROKER_URL`.
- **`transaction.on_commit()`**: Delays calling `.delay()` until the current database transaction successfully commits. This prevents a worker from processing a task before the related database changes are actually saved.
- **Multiple Redis instances**: Celery does not automatically discover or choose between arbitrary Redis servers. It uses the broker configured in `CELERY_BROKER_URL`. Multiple brokers can be configured for failover, while Redis Sentinel/Cluster or managed Redis can provide high availability.
- **Flow**: `Django → DB Commit → Celery → Configured Broker (Redis/RabbitMQ) → Worker → Task Execution`
---

## 8. Enterprise Resiliency & Idempotency (Phase 3)

In Phase 3, we transitioned from a simple task system to a resilient, enterprise-grade architecture. The primary goal was to prevent race conditions, guarantee tasks only run once (idempotency), maintain a strict audit trail, and handle failures gracefully.

### 8.1 The Service Layer & Database Locking (`tasks/services.py`)

Previously, our Celery worker updated the database directly (`task.status = "COMPLETED"`). This is dangerous if two workers accidentally pick up the same task at the exact same millisecond. We fixed this by centralizing all status changes into a single "Service" function.

#### Strict State Machines
```python
ALLOWED = {"PENDING": {"PROCESSING"}, "PROCESSING": {"COMPLETED"}}
```
* **Why it's done:** A task should never jump randomly from `COMPLETED` back to `PROCESSING`. By defining a strict mapping of allowed state transitions, we mathematically prevent illegal data states.

#### Row-Level Locking (`select_for_update`)
```python
@transaction.atomic
def transition(task_id, new_status, *, source, user=None, result=None):
    task = Task.objects.select_for_update().get(pk=task_id)
```
* **Concept:** Atomic Transactions & Row Locks.
* **Why it's done:** When updating a critical state, we must prevent concurrency issues.
  - `@transaction.atomic`: Wraps the entire function in a database transaction. If *anything* crashes inside this function, all database changes are completely rolled back (undone).
  - `select_for_update()`: Places a strict lock on this specific database row in PostgreSQL/MySQL. If Worker A and Worker B try to grab this task at the exact same millisecond, Worker A gets the lock. Worker B is forced to pause and wait until Worker A is completely finished (and the transaction commits) before it is allowed to read the row.

#### Guaranteeing Idempotency
```python
    if new_status not in ALLOWED.get(task.status, set()):
        raise ValueError(f"Illegal transition {task.status} -> {new_status}")
```
* **Concept:** Idempotent Operations.
* **Why it's done:** An idempotent operation means running it multiple times has the exact same effect as running it once. If Worker B gets the lock *after* Worker A finishes, Worker B sees the status is already `PROCESSING`. It tries to change it to `PROCESSING` again, which violates the `ALLOWED` rules. Raising a `ValueError` blocks duplicate execution and protects the system.

#### Automated Audit Trails (The Purpose of Auditing)

**The Problem:** When a database row only has a `status` field (like `status="COMPLETED"`), it only shows the *current* state. If a task gets stuck in `PROCESSING`, you have no idea if it got stuck 5 seconds ago or 5 weeks ago, wiping out all history of how it got there.

**The Solution:** An Audit Log records every single state transition in a separate historical ledger table. This provides:
1. **Traceability / Debugging:** You can see exactly how long a task took to go from `PENDING` to `PROCESSING`, and from `PROCESSING` to `COMPLETED`.
2. **Accountability:** By recording the `source` (e.g., `"CELERY"`, `"API"`, `"ADMIN"`), you know if the background worker finished the task naturally, or if an administrator manually forced it to complete via a dashboard.

```python
    AuditLog.objects.create(
        task=task, task_uuid=task.id, from_status=old, to_status=new_status, source=source
    )
```
* **How it works:** Because we centralized all status updates into the `transition()` function, it is **impossible for a developer to change a task's status without automatically generating an audit record.** Furthermore, because it is wrapped in `@transaction.atomic`, if the `AuditLog` fails to save (e.g., database runs out of space), the `task.status` change is instantly rolled back. They succeed together or fail together.

---

### 8.2 The Refactored Celery Worker (`tasks/tasks.py`)

Now that the service layer exists, we cleaned up the Celery worker to use it and handle errors securely.

```python
@shared_task(bind=True, acks_late=True, max_retries=3, default_retry_delay=5)
def process_task(self, task_id):
    try:
        task = transition(task_id, "PROCESSING", source="CELERY")
    except ValueError as e:
        logger.warning(f"Task {task_id} skipped: {e}")
        return str(task_id)
```
* **`acks_late=True`**: By default, Celery acknowledges a task the moment it starts. If the worker crashes (e.g. out of memory, server restart) mid-task, the task is lost forever. `acks_late=True` tells the broker (Redis) to keep the task in the queue until the worker successfully returns. If it crashes, the broker hands it to another worker.
* **Handling the `ValueError`**: Because of `acks_late`, duplicate task deliveries can happen. We purposely try to transition to `PROCESSING`. If we get a `ValueError`, it means another worker already claimed it. We catch the error, log a warning, and safely exit without crashing.

---

### 8.3 Protecting the API View (`tasks/views.py`)

```python
    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        task = self.get_object()
        
        if task.status != "PENDING":
            return Response(
                {"detail": "Task is not in PENDING state."}, 
                status=status.HTTP_409_CONFLICT
            )
```
* **Why it's done:** The frontend might accidentally send multiple clicks (double submit). By instantly checking `if task.status != "PENDING"`, we intercept duplicate requests and return a `409 Conflict`. We block it before it ever hits the Celery queue.

---

### 8.4 Custom Audit API Endpoint (`tasks/views.py`)

```python
    @action(detail=True, methods=['get'])
    def audit(self, request, pk=None):
        task = self.get_object()
        logs = AuditLog.objects.filter(task_uuid=task.id).order_by('-created_at')
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)
```
* **Concept:** Fetching Related Data via Custom Actions.
* **Why it's done:** Instead of creating a massive global `/api/auditlogs/` endpoint where users would have to filter out their own logs, we attach the `audit` action directly to the `TaskViewSet`. 
  - Because `detail=True`, it maps to `/api/tasks/<pk>/audit/`. 
  - Calling `self.get_object()` leverages our existing `get_queryset()` rules, meaning it automatically verifies the user actually owns the task before returning its audit history. It keeps the API clean and extremely secure by default.

---

### 8.5 Read-Only API Endpoints (`tasks/views.py`)

```python
class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    def get_queryset(self):
        return NotificationLog.objects.filter(user=self.request.user).order_by('-sent_at')
```
* **Concept:** Restricting API Access via Mixins.
* **Why it's done:** We don't want users to be able to create, edit, or delete system-generated notifications. Instead of using `ModelViewSet` (which automatically provides all 5 CRUD actions), we inherit from `GenericViewSet` and explicitly bolt on *only* `ListModelMixin` (GET all) and `RetrieveModelMixin` (GET one). This creates a completely secure, **Read-Only** endpoint.

---

## 9. Asynchronous Endpoints & ASGI (Phase 4)

In Phase 4, we upgraded our API to handle high-concurrency polling by introducing native asynchronous (`async`) views and running the server via ASGI.

### 9.1 The Need for ASGI and Uvicorn
* **Concept:** WSGI vs. ASGI (Web Server Gateway Interface vs. Asynchronous Server Gateway Interface).
* **Explanation:** Historically, Django runs under WSGI (via `python manage.py runserver` or Gunicorn). WSGI is strictly synchronous—each request locks up a Python thread until it finishes. If 100 users poll the API simultaneously, 100 threads are blocked, leading to a bottleneck. ASGI allows native asynchronous I/O (`async`/`await`). By switching to an ASGI server like **Uvicorn**, Django runs its event loop natively. When a request is waiting on the database, the server suspends it and handles other requests on the same thread, maximizing throughput.

### 9.2 Async JWT Authentication (`tasks/auth.py`)
```python
def jwt_required_async(view):
    async def wrapper(request, *a, **kw):
        try:
            result = await sync_to_async(_jwt.authenticate)(request)
        ...
```
* **Concept:** Bridging Sync and Async.
* **Why it's done:** Django REST Framework (DRF) is inherently synchronous and does not support `async def` views natively. We had to bypass DRF for our async endpoint. However, since the JWT authentication library (`SimpleJWT`) performs synchronous database queries, we used Django's `sync_to_async` utility. This safely executes the synchronous authentication logic in a background thread pool, preventing it from blocking the main async event loop, while allowing our wrapper to remain fully `async`.

### 9.3 The Async View (`tasks/async_views.py`)
```python
@jwt_required_async
async def task_status(request):
    rows = Task.objects.filter(owner=request.user, id__in=ids)\
                       .values("id", "status", "updated_at", "result_data")
                       
    data = [
        {**r, "id": str(r["id"]), "updated_at": r["updated_at"].isoformat()}
        async for r in rows
    ]
```
* **Concept:** Async ORM Evaluation.
* **Why it's done:** Django 4.1+ introduced support for native asynchronous database queries. By using `async for`, we instruct Django to execute the query without blocking the main thread. If we had used a standard synchronous `for r in rows:` inside an `async def` view, Django would raise a `SynchronousOnlyOperation` error to protect us from accidentally blocking the event loop.

### 9.4 Proving the Async Difference
If you want to prove the performance difference between standard WSGI (`runserver`) and ASGI (`uvicorn`) during an interview, you can describe a load test scenario:
1. **The Setup:** Add a forced `await asyncio.sleep(1)` inside the async view to simulate network latency or heavy I/O.
2. **The Load:** Send 100 concurrent requests to this endpoint (using a tool like `wrk` or `ab`).
3. **The Result (WSGI `runserver`):** The default `runserver` will process requests in a limited thread pool. Because the requests are forced to sleep synchronously on the threads, they bottleneck, and the 100 requests will take significantly longer than 1 second to clear.
4. **The Result (ASGI `uvicorn`):** Uvicorn runs in a single event loop. When it hits the `asyncio.sleep(1)`, it pauses that request, picks up the next one, pauses it, and so on. All 100 requests sleep concurrently without blocking threads, and the entire batch of 100 requests will finish in almost exactly ~1 second total.
