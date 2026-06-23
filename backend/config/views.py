from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404


def favicon(_request):
    """Serve favicon from collected static or source static dir."""
    candidates = [settings.STATIC_ROOT, *settings.STATICFILES_DIRS]
    for root in candidates:
        path = Path(root) / "img" / "spmi-logo.png"
        if path.is_file():
            return FileResponse(path.open("rb"), content_type="image/png")
    raise Http404
