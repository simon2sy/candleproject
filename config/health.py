"""Small operational endpoints for load balancers and uptime monitoring."""
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """Liveness probe: process is running and can serve HTTP."""
    return JsonResponse({"status": "ok"})


@require_GET
def readyz(request):
    """Readiness probe: verify the configured database is reachable."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "not_ready"}, status=503)
    return JsonResponse({"status": "ready"})
