from django.conf import settings


def patch_notes(request):
    return {
        "patch_notes_enabled": getattr(settings, "PATCH_NOTES_ENABLED", False),
    }
