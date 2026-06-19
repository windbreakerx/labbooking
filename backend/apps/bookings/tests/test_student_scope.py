import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.academics.models import Discipline, LabWork, Semester, StudentGroup
from apps.academics.querysets import (
    student_disciplines_qs,
    student_lab_works_qs,
    student_support_training_centers_qs,
)
from apps.bookings.services import BookingError, BookingService
from apps.scheduling.models import LabSession, LabSessionStatus, Room, TrainingCenter
from apps.users.models import User, UserRole


@pytest.fixture
def semester(db):
    return Semester.objects.create(
        name="Scope Test",
        start_date="2026-01-01",
        end_date="2026-12-31",
        is_active=True,
    )


@pytest.fixture
def own_discipline(semester):
    return Discipline.objects.create(title="Своя дисциплина", semester=semester, is_published=True)


@pytest.fixture
def foreign_discipline(semester):
    return Discipline.objects.create(title="Чужая дисциплина", semester=semester, is_published=True)


@pytest.fixture
def own_lab_work(own_discipline):
    return LabWork.objects.create(
        discipline=own_discipline,
        number=1,
        title="Своя ЛР",
        duration_minutes=90,
        is_published=True,
    )


@pytest.fixture
def foreign_lab_work(foreign_discipline):
    return LabWork.objects.create(
        discipline=foreign_discipline,
        number=1,
        title="Чужая ЛР",
        duration_minutes=90,
        is_published=True,
    )


@pytest.fixture
def student_group(own_discipline, own_lab_work):
    group = StudentGroup.objects.create(name="SCOPE-24")
    group.disciplines.add(own_discipline)
    group.lab_works.add(own_lab_work)
    return group


@pytest.fixture
def scoped_student(db, student_group):
    user = User.objects.create_user(
        email="scoped@stud.spmi.ru",
        password="pass",
        first_name="Scope",
        last_name="Student",
        role=UserRole.STUDENT,
    )
    user.profile.student_group = student_group
    user.profile.save(update_fields=["student_group"])
    return user


@pytest.fixture
def training_center(own_discipline, own_lab_work):
    tc = TrainingCenter.objects.create(number=7, name="Своя лаборатория")
    own_discipline.training_centers.add(tc)
    own_lab_work.training_centers.add(tc)
    return tc


@pytest.fixture
def foreign_training_center(foreign_discipline):
    tc = TrainingCenter.objects.create(number=8, name="Чужая лаборатория")
    foreign_discipline.training_centers.add(tc)
    return tc


@pytest.fixture
def room(training_center):
    return Room.objects.create(training_center=training_center, number="701", capacity=5)


@pytest.fixture
def foreign_session(foreign_lab_work, semester):
    tc = TrainingCenter.objects.create(number=9)
    room = Room.objects.create(training_center=tc, number="901", capacity=5)
    from datetime import datetime, time

    from django.utils import timezone

    tz = timezone.get_current_timezone()
    starts = timezone.make_aware(datetime(2026, 7, 7, 10, 35), tz)
    return LabSession.objects.create(
        lab_work=foreign_lab_work,
        room=room,
        semester=semester,
        starts_at=starts,
        ends_at=starts + timezone.timedelta(minutes=90),
        capacity=5,
        status=LabSessionStatus.OPEN,
    )


@pytest.mark.django_db
class TestStudentScopeQuerysets:
    def test_disciplines_limited_to_group(self, scoped_student, own_discipline, foreign_discipline):
        ids = set(student_disciplines_qs(scoped_student).values_list("pk", flat=True))
        assert own_discipline.pk in ids
        assert foreign_discipline.pk not in ids

    def test_lab_works_limited_to_group(self, scoped_student, own_lab_work, foreign_lab_work):
        ids = set(student_lab_works_qs(scoped_student).values_list("pk", flat=True))
        assert own_lab_work.pk in ids
        assert foreign_lab_work.pk not in ids

    def test_support_training_centers_limited(
        self,
        scoped_student,
        training_center,
        foreign_training_center,
    ):
        ids = set(student_support_training_centers_qs(scoped_student).values_list("pk", flat=True))
        assert training_center.pk in ids
        assert foreign_training_center.pk not in ids


@pytest.mark.django_db
class TestStudentScopeWeb:
    def test_disciplines_list_hides_foreign(self, scoped_student, own_discipline, foreign_discipline):
        client = Client()
        client.force_login(scoped_student)
        response = client.get("/disciplines/")
        assert response.status_code == 200
        assert own_discipline.title.encode() in response.content
        assert foreign_discipline.title.encode() not in response.content

    def test_foreign_discipline_lab_works_404(self, scoped_student, foreign_discipline):
        client = Client()
        client.force_login(scoped_student)
        response = client.get(f"/disciplines/{foreign_discipline.pk}/lab-works/")
        assert response.status_code == 404

    def test_foreign_lab_work_book_404(self, scoped_student, foreign_lab_work):
        client = Client()
        client.force_login(scoped_student)
        response = client.get(f"/lab-works/{foreign_lab_work.pk}/book/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestStudentScopeApi:
    def test_disciplines_api_scoped(self, scoped_student, own_discipline, foreign_discipline):
        client = APIClient()
        client.force_authenticate(user=scoped_student)
        response = client.get("/api/v1/disciplines/")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["results"]}
        assert own_discipline.pk in ids
        assert foreign_discipline.pk not in ids

    def test_foreign_discipline_lab_works_api_404(self, scoped_student, foreign_discipline):
        client = APIClient()
        client.force_authenticate(user=scoped_student)
        response = client.get(f"/api/v1/disciplines/{foreign_discipline.pk}/lab-works/")
        assert response.status_code == 404

    def test_session_filters_foreign_lab_work_404(self, scoped_student, foreign_lab_work):
        client = APIClient()
        client.force_authenticate(user=scoped_student)
        response = client.get(f"/api/v1/sessions/filters/?lab_work={foreign_lab_work.pk}")
        assert response.status_code == 404

    def test_booking_foreign_session_denied(self, scoped_student, foreign_session, monkeypatch):
        monkeypatch.setattr(
            "apps.bookings.services.session_availability.is_day_open_for_booking",
            lambda *_args, **_kwargs: True,
        )
        monkeypatch.setattr(
            "apps.bookings.services.booking.is_day_open_for_booking",
            lambda *_args, **_kwargs: True,
        )
        client = APIClient()
        client.force_authenticate(user=scoped_student)
        response = client.post(
            "/api/v1/bookings/",
            {"lab_session_id": foreign_session.pk},
            format="json",
        )
        assert response.status_code == 400
        assert "недоступна" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_booking_service_rejects_foreign_lab_work(scoped_student, foreign_session, monkeypatch):
    monkeypatch.setattr(
        "apps.bookings.services.booking.is_day_open_for_booking",
        lambda *_args, **_kwargs: True,
    )
    with pytest.raises(BookingError, match="недоступна"):
        BookingService(actor=scoped_student).create_booking(scoped_student, foreign_session.pk)
