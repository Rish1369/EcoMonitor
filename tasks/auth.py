from asgiref.sync import sync_to_async
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

_jwt = JWTAuthentication()

def jwt_required_async(view):
    async def wrapper(request, *a, **kw):
        try:
            result = await sync_to_async(_jwt.authenticate)(request)
        except AuthenticationFailed:
            result = None
        if not result:
            return JsonResponse({"detail": "Unauthorized"}, status=401)
        request.user = result[0]
        return await view(request, *a, **kw)
    return wrapper
