"""Shared pytest fixtures for bookings tests."""

from datetime import datetime, time

import pytest
from django.utils import timezone

from apps.academics.models import Discipline, LabWork, Semester, StudentGroup
from apps.scheduling.models import LabSession, LabSessionStatus, Room, TrainingCenter
from apps.users.models import User, UserRole


@pytest.fixture(autouse=True)
def _disable_day_open_gate(monkeypatch):
    monkeypatch.setattr(
        "apps.bookings.services.session_availability.is_day_open_for_booking",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "apps.bookings.services.booking.is_day_open_for_booking",
        lambda *_args, **_kwargs: True,
    )


def next_open_weekday_pair(days_ahead: int = 1, hour: int = 10, minute: int = 35):
    now = timezone.now()
    tz = timezone.get_current_timezone()
    for day_offset in range(days_ahead, 14):
        candidate_date = (now + timezone.timedelta(days=day_offset)).date()
        if candidate_date.weekday() >= 5:
            continue
        candidate = timezone.make_aware(
            datetime.combine(candidate_date, time(hour, minute)),
            tz,
        )
        if candidate <= now:
            continue
        return candidate
    raise RuntimeError("Не удалось подобрать открытую пару для теста.")


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


@pytest.fixture
def inactive_discipline(db):
    old_sem = Semester.objects.create(
        name="Old",
        start_date=timezone.now().date().replace(year=timezone.now().year - 1),
        end_date=timezone.now().date(),
        is_active=False,
    )
    return Discipline.objects.create(title="Старая", semester=old_sem, is_published=True)


@pytest.fixture
def lab_work(discipline):
    return LabWork.objects.create(
        discipline=discipline,
        number=1,
        title="ЛР 1",
        duration_minutes=90,
        is_published=True,
    )


@pytest.fixture
def room():
    tc = TrainingCenter.objects.create(number=1)
    return Room.objects.create(training_center=tc, number="101", capacity=2)


@pytest.fixture
def session(lab_work, room, semester):
    starts = next_open_weekday_pair(days_ahead=2, hour=10, minute=35)
    return LabSession.objects.create(
        lab_work=lab_work,
        room=room,
        semester=semester,
        starts_at=starts,
        ends_at=starts + timezone.timedelta(minutes=90),
        capacity=2,
        status=LabSessionStatus.OPEN,
    )


@pytest.fixture
def far_session(lab_work, room, semester):
    starts = timezone.now() + timezone.timedelta(days=20)
    starts = starts.replace(hour=10, minute=35, second=0, microsecond=0)
    return LabSession.objects.create(
        lab_work=lab_work,
        room=room,
        semester=semester,
        starts_at=starts,
        ends_at=starts + timezone.timedelta(minutes=90),
        capacity=5,
        status=LabSessionStatus.OPEN,
    )


@pytest.fixture
def student_group(discipline):
    group = StudentGroup.objects.create(name="TEST-24")
    group.disciplines.add(discipline)
    return group


@pytest.fixture
def student(db, student_group):
    user = User.objects.create_user(
        email="s@stud.spmi.ru",
        password="pass",
        first_name="A",
        last_name="B",
        role=UserRole.STUDENT,
    )
    user.profile.student_group = student_group
    user.profile.save(update_fields=["student_group"])
    return user


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        email="staff@spmi.ru",
        password="pass",
        first_name="S",
        last_name="T",
        role=UserRole.LAB_ADMIN,
        is_staff=True,
    )
