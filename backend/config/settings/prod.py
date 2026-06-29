from .base import *  # noqa: F403

DEBUG = False

# No insecure default in production — misconfigured deploy must fail at startup.
SECRET_KEY = env("SECRET_KEY")  # noqa: F405

# Первый выклад по HTTP: SECURE_SSL_REDIRECT=0. После HTTPS — включите в .env.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

_csrf_origins = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405
if not _csrf_origins:
    for host in ALLOWED_HOSTS:  # noqa: F405
        if host in ("localhost", "127.0.0.1"):
            continue
        if host.replace(".", "").isdigit():
            _csrf_origins.extend([f"http://{host}", f"https://{host}"])
        else:
            _csrf_origins.append(f"https://{host}")
CSRF_TRUSTED_ORIGINS = _csrf_origins

if SECURE_SSL_REDIRECT:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
