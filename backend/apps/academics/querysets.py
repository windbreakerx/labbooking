from django.db.models import Q

from apps.academics.models import Discipline, LabWork


def published_disciplines_qs():
    return Discipline.objects.filter(
        is_published=True,
        semester__is_active=True,
    )


def published_lab_works_qs(discipline_id: int):
    return LabWork.objects.filter(
        discipline_id=discipline_id,
        is_published=True,
        discipline__semester__is_active=True,
    )
