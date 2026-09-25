from django.http import JsonResponse
from .models import Task
from .auth import jwt_required_async

@jwt_required_async
async def task_status(request):
    ids = [i for i in request.GET.get("ids", "").split(",") if i][:50]
    if not ids:
        return JsonResponse({"detail": "ids required"}, status=400)
    
    rows = Task.objects.filter(owner=request.user, id__in=ids)\
                       .values("id", "status", "updated_at", "result_data")
                       
    data = [
        {**r, "id": str(r["id"]), "updated_at": r["updated_at"].isoformat()}
        async for r in rows
    ]
    return JsonResponse({"count": len(data), "results": data})
