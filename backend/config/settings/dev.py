from .base import *  # noqa: F403

DEBUG = True

# Локальный runserver на хосте: SQLite. В Docker — postgres (см. RUNNING_IN_DOCKER в compose).
if not env.bool("RUNNING_IN_DOCKER", default=False):  # noqa: F405
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
