"""
Django settings for the On-Demand Print Service.

Reads configuration from environment variables (a .env file in the backend/
directory is loaded automatically). See .env.example for every knob.
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: str = "False") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-key-change-me")
DEBUG = env_bool("DEBUG", "True")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost")

# ------------------------------------------------------------------ apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # local
    "apps.accounts",
    "apps.pricing",
    "apps.orders",
    "apps.payments",
    "apps.printing",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "print_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "print_service.wsgi.application"

# ------------------------------------------------------------- database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ----------------------------------------------------------------- auth
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

# --------------------------------------------------------------- i18n
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------- static / media
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- CORS
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

# ------------------------------------------------------------ business
MIN_PARTIAL_PERCENT = int(os.getenv("MIN_PARTIAL_PERCENT", "50"))
DUPLEX_DISCOUNT_FACTOR = float(os.getenv("DUPLEX_DISCOUNT_FACTOR", "0.90"))

# ---------------------------------------------------------------- Epson
EPSON_MOCK_MODE = env_bool("EPSON_MOCK_MODE", "True")
EPSON_API_BASE = os.getenv("EPSON_API_BASE", "https://api.epsonconnect.com/api/2")
EPSON_UPLOAD_BASE = os.getenv("EPSON_UPLOAD_BASE", "https://upload.epsonconnect.com")
EPSON_AUTH_BASE = os.getenv("EPSON_AUTH_BASE", "https://auth.epsonconnect.com")
EPSON_API_KEY = os.getenv("EPSON_API_KEY", "")
EPSON_CLIENT_ID = os.getenv("EPSON_CLIENT_ID", "")
EPSON_CLIENT_SECRET = os.getenv("EPSON_CLIENT_SECRET", "")
EPSON_DEVICE_GRANT = os.getenv("EPSON_DEVICE_GRANT", "password")
EPSON_DEVICE_EMAIL = os.getenv("EPSON_DEVICE_EMAIL", "")
EPSON_DEVICE_PASSWORD = os.getenv("EPSON_DEVICE_PASSWORD", "")
EPSON_DEVICE_REFRESH_TOKEN = os.getenv("EPSON_DEVICE_REFRESH_TOKEN", "")
EPSON_AUTH_CODE = os.getenv("EPSON_AUTH_CODE", "")
EPSON_PRINTER_NAME = os.getenv("EPSON_PRINTER_NAME", "Shop Printer")

# ------------------------------------------------------------ PayMongo
PAYMONGO_MOCK_MODE = env_bool("PAYMONGO_MOCK_MODE", "True")
PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY", "")
PAYMONGO_WEBHOOK_SECRET = os.getenv("PAYMONGO_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# --------------------------------------------------------------- email
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "printshop@example.com")

# Uploaded files are purged after this many days post-completion (PRD §6).
FILE_RETENTION_DAYS = int(os.getenv("FILE_RETENTION_DAYS", "30"))
MAX_UPLOAD_MB = 20  # Epson Connect upload limit

