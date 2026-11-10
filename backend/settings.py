import os
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY before running in production")
    secret_file = DATA_DIR / "django.secret"
    try:
        with secret_file.open("x", encoding="ascii") as handle:
            handle.write(secrets.token_urlsafe(48))
        secret_file.chmod(0o600)
    except FileExistsError:
        pass
    SECRET_KEY = secret_file.read_text(encoding="ascii").strip()
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
SETUP_TOKEN = os.getenv("SETUP_TOKEN", "")
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "rest_framework", "assets.apps.AssetsConfig",
]
MIDDLEWARE = [
    "backend.middleware.RemoveServerHeadersMiddleware",
    "backend.middleware.ContentSecurityPolicyMiddleware",
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "backend.urls"
WSGI_APPLICATION = "backend.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "dist"],
              "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request"]}}]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                         "NAME": os.getenv("DATABASE_PATH", str(DATA_DIR / "django.sqlite3")),
                         "OPTIONS": {"timeout": 30}}}
AUTH_USER_MODEL = "assets.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_ROOT = BASE_DIR / "dist"
SESSION_COOKIE_NAME = "asset.sid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_HEADER_NAME = "HTTP_X_CSRF_TOKEN"
CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
CSRF_FAILURE_VIEW = "assets.views.csrf_failure"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
if os.getenv("TRUST_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PARSER_CLASSES": ["assets.parsers.BoundedJSONParser", "rest_framework.parsers.FormParser", "rest_framework.parsers.MultiPartParser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "assets.views.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {"auth": "30/hour", "reminder": "6/min"},
}
MAX_REQUEST_BODY_SIZE = int(os.getenv("MAX_REQUEST_BODY_SIZE", str(10 * 1024 * 1024)))
CACHES = {"default": {
    "BACKEND": "django.core.cache.backends.redis.RedisCache" if os.getenv("REDIS_URL") else "django.core.cache.backends.locmem.LocMemCache",
    "LOCATION": os.getenv("REDIS_URL") or "assetcairn-local",
}}
SMTP_ALLOWED_HOSTS = [host.strip().lower() for host in os.getenv("SMTP_ALLOWED_HOSTS", os.getenv("SMTP_HOST", "")).split(",") if host.strip()]
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("SMTP_HOST", "")
EMAIL_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.getenv("SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("SMTP_PASS", "")
EMAIL_USE_SSL = os.getenv("SMTP_SECURE", "false").lower() == "true"
EMAIL_USE_TLS = not EMAIL_USE_SSL
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = os.getenv("SMTP_FROM", "")
REMINDERS_SMTP_CONFIGURED = bool(EMAIL_HOST and DEFAULT_FROM_EMAIL and bool(EMAIL_HOST_USER) == bool(EMAIL_HOST_PASSWORD))