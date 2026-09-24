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
