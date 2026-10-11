"""Fusion-Integrated — base settings.

Every value comes from the environment. This service holds NO user table:
identity, RBAC and directory data all come from Fusion_System_Administrator
over HTTP — see fusion_auth/.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_env_file(path):
    """Fill in from .env whatever the environment has not already set.

    Local development only in practice: production passes real variables
    through systemd, and setdefault means those always win. Without this,
    `cp .env.example .env` does nothing and every entry point depends on one
    shell's exports.
    """
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


_load_env_file(BASE_DIR / ".env")


def env(name, default=None):
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else v.strip()


def env_bool(name, default=False):
    raw = env(name)
    return default if raw is None else raw.lower() in ("1", "true", "yes", "on")


def env_int(name, default=None):
    raw = env(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def env_list(name, default=None):
    raw = env(name)
    if raw is None:
        return list(default or [])
    return [x.strip() for x in raw.split(",") if x.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

# django.contrib.auth is here because DRF needs it; fusion_auth authenticates.
DJANGO_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
]

# No models. Installed so its AppConfig runs and registers the session checks.
LOCAL_APPS = [
    "fusion_auth",
]

# Each module is an independent Django app: own tables, migrations and contract.
PLATFORM_MODULES = [
    "modules.directory",         # who people are, projected from IAM
    "modules.accesscontrol",     # which modules a role may enter
]

# See docs/03-platform/module-authoring-guide.md to add one.
DOMAIN_MODULES = [
    "modules.placement",
    "modules.elm",
]

INSTALLED_APPS = (DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
                  + PLATFORM_MODULES + DOMAIN_MODULES)

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.observability.middleware.RequestIDMiddleware",
    "django.middleware.common.CommonMiddleware",
    # X_FRAME_OPTIONS is inert without this; only this middleware emits it.
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# No CsrfViewMiddleware: core/api/csrf.py does it from the authentication classes.

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

# One database, owned by this service; person data comes from modules.directory.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "fusion_integrated"),
        "USER": env("DB_USER", "fusion_admin"),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "5432"),
        # MUST stay 0 under PgBouncer transaction pooling, which leaks session state.
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 0),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

#: How long a cached directory row may be trusted before it is refetched.
DIRECTORY_MAX_AGE_SECONDS = env_int("DIRECTORY_MAX_AGE_SECONDS", 6 * 60 * 60)

# The IAM. This service is a client of it and caches nothing it cannot rebuild.
IAM_BASE_URL = env("IAM_BASE_URL", "http://127.0.0.1:8001")
IAM_API_PREFIX = env("IAM_API_PREFIX", "/api")
IAM_SERVICE_TOKEN = env("IAM_SERVICE_TOKEN", "")
IAM_TIMEOUT_SECONDS = env_int("IAM_TIMEOUT_SECONDS", 5)
IAM_SESSION_CACHE_SECONDS = env_int("IAM_SESSION_CACHE_SECONDS", 60)
IAM_AUTH_COOKIE_NAME = env("IAM_AUTH_COOKIE_NAME", "fusion_session")

CACHES = {
    "default": (
        {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": env("REDIS_CACHE_URL"),
        }
        if env("REDIS_CACHE_URL")
        else {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "fusion-integrated",
        }
    )
}

CELERY_BROKER_URL = env("REDIS_BROKER_URL", "memory://")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Console by default, so a laptop never mails 3,000 students by accident.
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND",
                    "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL",
                         "Placement Cell <placement@iiitdmj.ac.in>")

#: Ceiling per worker pass, so a runaway loop cannot mail the institute.
NOTIFY_MAX_PER_RUN = env_int("NOTIFY_MAX_PER_RUN", 500)
#: Attempts before a notification is parked as failed for a human to look at.
NOTIFY_MAX_ATTEMPTS = env_int("NOTIFY_MAX_ATTEMPTS", 5)
#: A dozen events a day is legitimate during a drive; thirty is a bug.
NOTIFY_DAILY_CAP_PER_RECIPIENT = env_int("NOTIFY_DAILY_CAP_PER_RECIPIENT", 20)

#: Pre-Drive uploads, still served but never written; outside BASE_DIR or boot fails.
PLACEMENT_UPLOAD_ROOT = env(
    "PLACEMENT_UPLOAD_ROOT",
    str(Path.home() / ".local" / "share" / "fusion-integrated" / "uploads"))
#: When set, legacy reads go to nginx via X-Accel-Redirect. Must be `internal;`.
PLACEMENT_UPLOAD_INTERNAL_PREFIX = env("PLACEMENT_UPLOAD_INTERNAL_PREFIX", "")

# No multipart endpoints remain, so this only caps the JSON body.
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "fusion_auth.authentication.IamSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "fusion_auth.permissions.IsAuthenticatedPrincipal",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.api.pagination.CursorPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "EXCEPTION_HANDLER": "core.api.exceptions.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
    # Unset, DRF throttles on the whole client-controlled X-Forwarded-For.
    "NUM_PROXIES": env_int("DJANGO_NUM_PROXIES", 1),
    # Not DRF's ScopedRateThrottle: it keys on request.user.pk, absent here.
    "DEFAULT_THROTTLE_CLASSES": ["core.api.throttling.PrincipalScopedThrottle"],
    # Only endpoints opting in via `throttle_scope` are limited.
    "DEFAULT_THROTTLE_RATES": {
        "recruiter_login": "5/min",
        "recruiter_invite_accept": "10/hour",
        "apply": "30/hour",
        "export": "5/hour",
        "upload": "20/hour",
        "directory_search": "120/hour",
    },
}

# Recruiter passwords only; PBKDF2 verifies an older hash, then upgrades it.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

SPECTACULAR_SETTINGS = {
    "TITLE": "Fusion-Integrated API",
    "DESCRIPTION": "Non-academic platform. Independent modules, one login.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS", ["http://localhost:5173"])
CORS_ALLOW_CREDENTIALS = True

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
# After TIME_ZONE, which it reads, or a crontab entry fires at the wrong hour.
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
# SAMEORIGIN, not DENY: Fusion-client embeds these screens, same origin in prod.
X_FRAME_OPTIONS = "SAMEORIGIN"

# W003: CSRF is enforced by core/api/csrf.py. See the note above MIDDLEWARE.
# W019: the portal frames these screens deliberately, and only same origin.
SILENCED_SYSTEM_CHECKS = ["security.W003", "security.W019"]

# Without this, nothing is configured and every INFO audit line is discarded.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        # Raise the level to quiet a host down; do not remove the handler.
        "fusion": {"level": env("FUSION_LOG_LEVEL", "INFO"), "propagate": True},
    },
}
