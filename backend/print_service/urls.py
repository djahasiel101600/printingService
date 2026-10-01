from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve as static_serve


def health(_request):
    """Lightweight liveness probe used by the container healthcheck / tunnel."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health/", health, name="health"),
    path("django-admin/", admin.site.urls),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.pricing.urls")),
    path("api/", include("apps.orders.urls")),
    path("api/", include("apps.payments.urls")),
    path("api/", include("apps.printing.urls")),
]

# Serve collected static (Django admin assets) and uploaded media in every
# environment. With DEBUG=False the dev-only `static()` helper is a no-op, so
# the reverse proxy (nginx / cloudflared) forwards /static and /media here.
urlpatterns += [
    re_path(r"^static/(?P<path>.*)$", static_serve, {"document_root": str(settings.STATIC_ROOT)}),
    re_path(r"^media/(?P<path>.*)$", static_serve, {"document_root": str(settings.MEDIA_ROOT)}),
]
