import pytest
from datetime import datetime, time, timedelta
from django.core import mail
from django.test import Client, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import Discipline, LabWork, Semester
from apps.bookings.models import BookingStatus, SupportMessage, SupportTicket
from apps.bookings.services import BookingError, BookingService
from apps.bookings.services.session_availability import (
    bookable_sessions_qs,
    is_day_open_for_booking,
)
from apps.scheduling.models import LabSession, LabSessionStatus, Room, TrainingCenter
from apps.users.models import User, UserRole


@pytest.fixture(autouse=True)
def _disable_day_open_gate(monkeypatch):
    monkeypatch.setattr("apps.bookings.services.session_availability.is_day_open_for_booking", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("apps.bookings.services.booking.is_day_open_for_booking", lambda *_args, **_kwargs: True)


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
        starts2 = session.starts_at
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

    def test_manual_booking_skips_limits(self, student, session, staff):
        BookingService(actor=staff).create_booking(student, session.pk)
        service = BookingService(actor=staff)
        booking = service.create_booking(
            student,
            session.pk,
            manual=True,
            skip_student_rules=True,
        )
        assert booking.registration_type == "MANUAL"

    def test_cancel_within_deadline(self, student, session):
        service = BookingService(actor=student)
        booking = service.create_booking(student, session.pk)
        cancelled = service.cancel_booking(booking)
        assert cancelled.current_status == BookingStatus.CANCELLED

    @override_settings(BOOKING_CANCEL_HOURS=200)
    def test_cancel_after_deadline_denied(self, student, session):
        session.ends_at = session.starts_at + timezone.timedelta(minutes=90)
        session.save()
        service = BookingService(actor=student)
        booking = service.create_booking(student, session.pk)
        with pytest.raises(BookingError, match="200"):
            service.cancel_booking(booking)

    def test_room_parallel_capacity_limit(self, student, session, lab_work, room, semester):
        other_student = User.objects.create_user(
            email="s2@stud.spmi.ru",
            password="pass",
            first_name="I",
            last_name="II",
            role=UserRole.STUDENT,
        )
        third_student = User.objects.create_user(
            email="s3@stud.spmi.ru",
            password="pass",
            first_name="III",
            last_name="IV",
            role=UserRole.STUDENT,
        )
        second_lab_work = LabWork.objects.create(
            discipline=lab_work.discipline,
            number=2,
            title="ЛР 2",
            duration_minutes=90,
            is_published=True,
        )
        parallel_session = LabSession.objects.create(
            lab_work=second_lab_work,
            room=room,
            semester=semester,
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            capacity=2,
            status=LabSessionStatus.OPEN,
        )
        BookingService().create_booking(student, session.pk)
        BookingService().create_booking(other_student, parallel_session.pk)
        with pytest.raises(BookingError, match="Аудитория"):
            BookingService().create_booking(third_student, parallel_session.pk)

    def test_staff_status_change(self, student, session, staff):
        booking = BookingService(actor=student).create_booking(student, session.pk)
        updated = BookingService(actor=staff).change_status(
            booking,
            BookingStatus.VISITED,
        )
        assert updated.current_status == BookingStatus.VISITED

    def test_booking_sends_email(self, student, session):
        mail.outbox.clear()
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            BookingService(actor=student).create_booking(student, session.pk)
        assert len(mail.outbox) == 1
        assert "записаны" in mail.outbox[0].body.lower()

    def test_create_booking_calls_room_overlap_lock(self, student, session, monkeypatch):
        called = {"count": 0, "session_id": None}
        original_lock = BookingService._lock_overlapping_room_sessions

        def lock_spy(self, locked_session):
            called["count"] += 1
            called["session_id"] = locked_session.pk
            return original_lock(self, locked_session)

        monkeypatch.setattr(BookingService, "_lock_overlapping_room_sessions", lock_spy)

        BookingService(actor=student).create_booking(student, session.pk)
        assert called["count"] == 1
        assert called["session_id"] == session.pk


@pytest.mark.django_db
class TestSessionAvailability:
    def test_horizon_excludes_far_sessions(self, session, far_session, lab_work):
        qs = bookable_sessions_qs(lab_work_id=lab_work.pk)
        assert session in qs
        assert far_session not in qs

    def test_day_opens_at_rule(self):
        session_date = (timezone.now() + timezone.timedelta(days=5)).date()
        before_open = timezone.make_aware(
            datetime.combine(
                session_date - timedelta(days=1),
                time(21, 0),
            ),
            timezone.get_current_timezone(),
        )
        assert is_day_open_for_booking(session_date, before_open) is False

    def test_only_weekday_pair_sessions_are_bookable(self, lab_work, room, semester):
        weekday_pair = next_open_weekday_pair(hour=10, minute=35)
        weekend_pair = weekday_pair
        while weekend_pair.weekday() != 5:
            weekend_pair += timezone.timedelta(days=1)
        non_pair_weekday = weekday_pair.replace(hour=11, minute=0)

        s1 = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=weekday_pair,
            ends_at=weekday_pair + timezone.timedelta(minutes=90),
            capacity=2,
            status=LabSessionStatus.OPEN,
        )
        s2 = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=weekend_pair,
            ends_at=weekend_pair + timezone.timedelta(minutes=90),
            capacity=2,
            status=LabSessionStatus.OPEN,
        )
        s3 = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=non_pair_weekday,
            ends_at=non_pair_weekday + timezone.timedelta(minutes=90),
            capacity=2,
            status=LabSessionStatus.OPEN,
        )

        qs = bookable_sessions_qs(lab_work_id=lab_work.pk)
        assert s1 in qs
        assert s2 not in qs
        assert s3 not in qs


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


@pytest.mark.django_db
def test_session_filters_api(student, session, lab_work):
    client = APIClient()
    client.force_authenticate(user=student)
    response = client.get(f"/api/v1/sessions/filters/?lab_work={lab_work.pk}")
    assert response.status_code == 200
    assert response.json()["level"] == "date"
    assert len(response.json()["options"]) >= 1


@pytest.mark.django_db
def test_manual_booking_api(staff, student, session):
    client = APIClient()
    client.force_authenticate(user=staff)
    response = client.post(
        "/api/v1/admin/bookings/manual/",
        {"student_id": student.pk, "lab_session_id": session.pk},
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_support_message_api(student, staff):
    ticket = SupportTicket.objects.create(
        student=student,
        subject="Проблема",
        body="Не работает",
    )
    client = APIClient()
    client.force_authenticate(user=staff)
    response = client.post(
        f"/api/v1/support/tickets/{ticket.pk}/messages/",
        {"body": "Мы разберёмся"},
        format="json",
    )
    assert response.status_code == 201
    assert SupportMessage.objects.filter(ticket=ticket).count() == 1


@pytest.mark.django_db
def test_disciplines_active_semester_only(student, discipline, inactive_discipline):
    client = Client()
    client.force_login(student)
    response = client.get("/disciplines/")
    assert response.status_code == 200
    assert discipline.title.encode() in response.content
    assert inactive_discipline.title.encode() not in response.content


@pytest.mark.django_db
def test_book_page_student_only(staff, lab_work):
    client = Client()
    client.force_login(staff)
    response = client.get(f"/lab-works/{lab_work.pk}/book/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_staff_bookings_filters_and_manual_web(staff, student, session):
    client = Client()
    client.force_login(staff)
    response = client.get("/staff/bookings/", {"student": student.email})
    assert response.status_code == 200

    response = client.post(
        "/staff/bookings/manual/",
        {"student_email": student.email, "session_id": session.pk},
    )
    assert response.status_code == 302
    assert student.bookings.filter(lab_session=session).exists()


@pytest.mark.django_db
def test_staff_lab_scope_hides_foreign_booking(staff, student, session, room):
    staff.profile.training_center = room.training_center
    staff.profile.save(update_fields=["training_center"])
    other_tc = TrainingCenter.objects.create(number=99)
    other_room = Room.objects.create(training_center=other_tc, number="999", capacity=5)
    other_session = LabSession.objects.create(
        lab_work=session.lab_work,
        room=other_room,
        semester=session.semester,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        capacity=5,
        status=LabSessionStatus.OPEN,
    )
    BookingService(actor=staff).create_booking(
        student,
        other_session.pk,
        manual=True,
        skip_student_rules=True,
    )
    client = Client()
    client.force_login(staff)
    response = client.get("/staff/bookings/")
    assert response.status_code == 200
    assert other_room.number.encode() not in response.content
