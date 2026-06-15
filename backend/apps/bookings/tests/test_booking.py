import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import Discipline, LabWork, Semester
from apps.bookings.models import BookingStatus
from apps.bookings.services import BookingError, BookingService
from apps.scheduling.models import LabSession, LabSessionStatus, Room, TrainingCenter
from apps.users.models import User, UserRole


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
    starts = timezone.now() + timezone.timedelta(days=3)
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
def student(db):
    user = User.objects.create_user(
        email="s@stud.spmi.ru",
        password="pass",
        first_name="A",
        last_name="B",
        role=UserRole.STUDENT,
    )
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


@pytest.mark.django_db
class TestBookingService:
    def test_create_booking(self, student, session):
        booking = BookingService(actor=student).create_booking(student, session.pk)
        assert booking.current_status == BookingStatus.BOOKED

    def test_capacity_limit(self, student, session, db):
        other = User.objects.create_user(
            email="o@stud.spmi.ru",
            password="p",
            first_name="O",
            last_name="T",
            role=UserRole.STUDENT,
        )
        third = User.objects.create_user(
            email="t@stud.spmi.ru",
            password="p",
            first_name="T",
            last_name="H",
            role=UserRole.STUDENT,
        )
        BookingService().create_booking(student, session.pk)
        BookingService().create_booking(other, session.pk)
        with pytest.raises(BookingError, match="Нет свободных мест"):
            BookingService().create_booking(third, session.pk)

    def test_one_booking_per_discipline(self, student, session, lab_work, room, semester):
        BookingService().create_booking(student, session.pk)
        starts2 = timezone.now() + timezone.timedelta(days=4)
        session2 = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=starts2,
            ends_at=starts2 + timezone.timedelta(minutes=90),
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        with pytest.raises(BookingError, match="активная запись"):
            BookingService().create_booking(student, session2.pk)

    def test_cancel_within_deadline(self, student, session):
        service = BookingService(actor=student)
        booking = service.create_booking(student, session.pk)
        cancelled = service.cancel_booking(booking)
        assert cancelled.current_status == BookingStatus.CANCELLED

    def test_cancel_after_deadline_denied(self, student, session):
        session.starts_at = timezone.now() + timezone.timedelta(hours=2)
        session.ends_at = session.starts_at + timezone.timedelta(minutes=90)
        session.save()
        service = BookingService(actor=student)
        booking = service.create_booking(student, session.pk)
        with pytest.raises(BookingError, match="24"):
            service.cancel_booking(booking)


@pytest.mark.django_db
def test_health_endpoint():
    client = APIClient()
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.django_db
def test_api_booking_flow(student, session):
    client = APIClient()
    client.force_authenticate(user=student)
    response = client.post("/api/v1/bookings/", {"lab_session_id": session.pk}, format="json")
    assert response.status_code == 201
    bookings = client.get("/api/v1/me/bookings/")
    assert bookings.status_code == 200
    assert bookings.json()["count"] == 1
