"""Root URLs.

Every module mounts itself under /api/v1/<module>/. A module that is not in
INSTALLED_APPS contributes no URLs at all — that is what "independent" means
here: removing a module is deleting a directory and one settings line.
"""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

import core.api.schema  # noqa: F401  registers the auth schemes by import
from core.api.health import healthz, readyz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    path("api/v1/", include("fusion_auth.urls")),
    path("api/v1/directory/", include("modules.directory.api.urls")),
    path("api/v1/placement/", include("modules.placement.api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/v1/elm/", include("modules.elm.api.urls")),
]
