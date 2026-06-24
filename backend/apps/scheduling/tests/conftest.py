"""Fixtures for scheduling app tests."""

import pytest
from django.utils import timezone

from apps.academics.models import Discipline, Semester


@pytest.fixture
def semester(db):
    return Semester.objects.create(
        name="Test",
        start_date=timezone.now().date(),
        end_date=timezone.now().date().replace(year=timezone.now().year + 1),
        is_active=True,
    )


@pytest.fixture
def discipline(semester):
    return Discipline.objects.create(title="Физика", semester=semester, is_published=True)
