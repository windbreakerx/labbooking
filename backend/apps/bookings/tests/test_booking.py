import pytest
from datetime import date, datetime, timedelta
from django.core import mail
from django.db.utils import OperationalError
from django.test import Client, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import Discipline, LabWork
from apps.bookings.models import BookingStatus, SupportMessage, SupportTicket
from apps.bookings.services import BookingError, BookingService
from apps.bookings.services.session_availability import (
    booking_date_window,
    bookable_sessions_qs,
    is_day_open_for_booking,
    is_pair_time_for_booking,
)
from apps.bookings.tests.conftest import create_lab_work, next_open_weekday_pair
from apps.scheduling.models import LabSession, LabSessionStatus, LabStand, Room, TrainingCenter
from apps.users.models import User, UserRole


def _assign_student_group(user, student_group):
    user.profile.student_group = student_group
    user.profile.save(update_fields=["student_group"])
    return user


@pytest.mark.django_db
class TestBookingService:
    def test_create_booking(self, student, session):
        booking = BookingService(actor=student).create_booking(student, session.pk)
        assert booking.current_status == BookingStatus.BOOKED

    def test_capacity_limit(self, student, session, db, student_group):
        other = _assign_student_group(
            User.objects.create_user(
                email="o@stud.spmi.ru",
                password="p",
                first_name="O",
                last_name="T",
                role=UserRole.STUDENT,
            ),
            student_group,
        )
        third = _assign_student_group(
            User.objects.create_user(
                email="t@stud.spmi.ru",
                password="p",
                first_name="T",
                last_name="H",
                role=UserRole.STUDENT,
            ),
            student_group,
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

    def test_manual_booking_skips_limits(self, student, session, staff, lab_work, room, semester):
        BookingService().create_booking(student, session.pk)
        starts2 = session.starts_at + timedelta(days=7)
        while timezone.localtime(starts2).weekday() >= 5:
            starts2 += timedelta(days=1)
        session2 = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=starts2,
            ends_at=starts2 + timedelta(minutes=90),
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        service = BookingService(actor=staff)
        booking = service.create_booking(
            student,
            session2.pk,
            manual=True,
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

    def test_room_parallel_capacity_limit(self, student, session, lab_work, discipline, room, semester, student_group):
        other_student = _assign_student_group(
            User.objects.create_user(
                email="s2@stud.spmi.ru",
                password="pass",
                first_name="I",
                last_name="II",
                role=UserRole.STUDENT,
            ),
            student_group,
        )
        third_student = _assign_student_group(
            User.objects.create_user(
                email="s3@stud.spmi.ru",
                password="pass",
                first_name="III",
                last_name="IV",
                role=UserRole.STUDENT,
            ),
            student_group,
        )
        second_lab_work = create_lab_work(
            discipline,
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

    def test_same_lab_parallel_capacity_limit(self, student, session, room, semester, student_group):
        room.capacity = 10
        room.save(update_fields=["capacity"])
        session.capacity = 3
        session.save(update_fields=["capacity"])
        session.lab_work.capacity = 3
        session.lab_work.save(update_fields=["capacity"])

        second_student = _assign_student_group(
            User.objects.create_user(
                email="same-lab-2@stud.spmi.ru",
                password="pass",
                first_name="S2",
                last_name="Student",
                role=UserRole.STUDENT,
            ),
            student_group,
        )
        third_student = _assign_student_group(
            User.objects.create_user(
                email="same-lab-3@stud.spmi.ru",
                password="pass",
                first_name="S3",
                last_name="Student",
                role=UserRole.STUDENT,
            ),
            student_group,
        )
        fourth_student = _assign_student_group(
            User.objects.create_user(
                email="same-lab-4@stud.spmi.ru",
                password="pass",
                first_name="S4",
                last_name="Student",
                role=UserRole.STUDENT,
            ),
            student_group,
        )

        overlap = LabSession.objects.create(
            lab_work=session.lab_work,
            room=room,
            semester=semester,
            starts_at=session.starts_at + timezone.timedelta(minutes=30),
            ends_at=session.starts_at + timezone.timedelta(minutes=75),
            capacity=3,
            status=LabSessionStatus.OPEN,
        )

        BookingService().create_booking(student, session.pk)
        BookingService().create_booking(second_student, session.pk)
        BookingService().create_booking(third_student, session.pk)

        assert overlap.available_seats == 0
        with pytest.raises(BookingError, match="Лимит мест для этой лабораторной работы"):
            BookingService().create_booking(fourth_student, overlap.pk)

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

    def test_booking_email_error_is_logged_without_rollback(self, student, session, monkeypatch, caplog):
        def fail_send_mail(*_args, **_kwargs):
            raise RuntimeError("smtp down")

        monkeypatch.setattr("apps.bookings.services.booking.send_mail", fail_send_mail)
        with override_settings(EMAIL_FAIL_SILENTLY=False):
            booking = BookingService(actor=student).create_booking(student, session.pk)

        assert booking.pk
        assert "Failed to send booking email" in caplog.text

    def test_create_booking_calls_booking_lock(self, student, session, monkeypatch):
        called = {"count": 0, "session_id": None, "lock_ids": None}
        original_lock = BookingService._lock_for_booking

        def lock_spy(self, locked_session):
            called["count"] += 1
            called["session_id"] = locked_session.pk
            called["lock_ids"] = self._collect_booking_lock_ids(locked_session)
            return original_lock(self, locked_session)

        monkeypatch.setattr(BookingService, "_lock_for_booking", lock_spy)

        BookingService(actor=student).create_booking(student, session.pk)
        assert called["count"] == 1
        assert called["session_id"] == session.pk
        assert called["lock_ids"] == [session.pk]

    def test_create_booking_retries_on_deadlock(self, student, session, monkeypatch):
        attempts = {"count": 0}
        original_create = BookingService._create_booking_in_transaction

        def flaky_create(self, *args, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise OperationalError("deadlock detected")
            return original_create(self, *args, **kwargs)

        monkeypatch.setattr(BookingService, "_create_booking_in_transaction", flaky_create)
        monkeypatch.setattr("apps.bookings.services.booking.time.sleep", lambda *_args: None)

        booking = BookingService(actor=student).create_booking(student, session.pk)
        assert booking.pk
        assert attempts["count"] == 2

    def test_shared_stand_blocks_parallel_booking(
        self,
        student,
        session,
        room,
        semester,
        student_group,
    ):
        stand = LabStand.objects.create(
            name="Общий стенд",
            inventory_number="ST-001",
            training_center=room.training_center,
            room=room,
        )
        session.lab_work.primary_stand = stand
        session.lab_work.save(update_fields=["primary_stand"])

        discipline_two = Discipline.objects.create(
            title="Вторая дисциплина",
            semester=semester,
            is_published=True,
        )
        student_group.disciplines.add(discipline_two)
        second_lab = create_lab_work(
            discipline_two,
            number=1,
            title="ЛР на том же стенде",
            duration_minutes=90,
            is_published=True,
            primary_stand=stand,
        )
        second_session = LabSession.objects.create(
            lab_work=second_lab,
            room=room,
            semester=semester,
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            capacity=2,
            status=LabSessionStatus.OPEN,
        )
        other_student = _assign_student_group(
            User.objects.create_user(
                email="stand-conflict@stud.spmi.ru",
                password="pass",
                first_name="S",
                last_name="C",
                role=UserRole.STUDENT,
            ),
            student_group,
        )
        BookingService().create_booking(student, session.pk)
        with pytest.raises(BookingError, match="Стенд уже занят"):
            BookingService().create_booking(other_student, second_session.pk)

    def test_shared_stand_allows_multiple_students_on_same_lab_session(
        self,
        student,
        session,
        room,
        student_group,
    ):
        stand = LabStand.objects.create(
            name="Стенд для группы",
            inventory_number="ST-002",
            training_center=room.training_center,
            room=room,
        )
        session.lab_work.primary_stand = stand
        session.lab_work.save(update_fields=["primary_stand"])
        session.capacity = 3
        session.save(update_fields=["capacity"])

        second_student = _assign_student_group(
            User.objects.create_user(
                email="stand-group@stud.spmi.ru",
                password="pass",
                first_name="G",
                last_name="R",
                role=UserRole.STUDENT,
            ),
            student_group,
        )
        third_student = _assign_student_group(
            User.objects.create_user(
                email="stand-group2@stud.spmi.ru",
                password="pass",
                first_name="G",
                last_name="R2",
                role=UserRole.STUDENT,
            ),
            student_group,
        )

        BookingService().create_booking(student, session.pk)
        BookingService().create_booking(second_student, session.pk)
        BookingService().create_booking(third_student, session.pk)

        assert session.available_seats == 0

    def test_shared_stand_does_not_cap_available_seats_to_one(
        self,
        session,
        room,
    ):
        stand = LabStand.objects.create(
            name="Стенд без записей",
            inventory_number="ST-003",
            training_center=room.training_center,
            room=room,
        )
        session.lab_work.primary_stand = stand
        session.lab_work.save(update_fields=["primary_stand"])
        session.capacity = 3
        session.save(update_fields=["capacity"])

        assert session.available_seats == 3

    def test_student_cannot_book_overlapping_intervals(
        self,
        student,
        session,
        semester,
        student_group,
    ):
        other_tc = TrainingCenter.objects.create(number=77)
        other_room = Room.objects.create(training_center=other_tc, number="777", capacity=10)
        discipline_two = Discipline.objects.create(
            title="Термодинамика",
            semester=semester,
            is_published=True,
        )
        student_group.disciplines.add(discipline_two)
        second_lab = create_lab_work(
            discipline_two,
            number=1,
            title="ЛР 2",
            duration_minutes=60,
            is_published=True,
        )
        overlapping_session = LabSession.objects.create(
            lab_work=second_lab,
            room=other_room,
            semester=semester,
            starts_at=session.starts_at + timezone.timedelta(minutes=30),
            ends_at=session.ends_at + timezone.timedelta(minutes=30),
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        BookingService().create_booking(student, session.pk)
        with pytest.raises(BookingError, match="пересекающееся время"):
            BookingService().create_booking(student, overlapping_session.pk)


@pytest.mark.django_db
class TestSessionAvailability:
    def test_horizon_excludes_far_sessions(self, session, far_session, lab_work):
        qs = bookable_sessions_qs(lab_work_id=lab_work.pk)
        assert session in qs
        assert far_session not in qs

    def test_booking_window_shift_1500_and_2200(self):
        tz = timezone.get_current_timezone()
        now_early = timezone.make_aware(datetime(2026, 7, 1, 14, 0), tz)
        now_after_close = timezone.make_aware(datetime(2026, 7, 1, 15, 1), tz)
        now_after_open = timezone.make_aware(datetime(2026, 7, 1, 22, 1), tz)

        min_early, max_early = booking_date_window(now_early)
        assert min_early == date(2026, 7, 2)
        assert max_early == date(2026, 7, 15)

        min_close, max_close = booking_date_window(now_after_close)
        assert min_close == date(2026, 7, 3)
        assert max_close == date(2026, 7, 15)

        min_open, max_open = booking_date_window(now_after_open)
        assert min_open == date(2026, 7, 3)
        assert max_open == date(2026, 7, 16)

        assert is_day_open_for_booking(date(2026, 7, 2), now_early) is True
        assert is_day_open_for_booking(date(2026, 7, 2), now_after_close) is False
        assert is_day_open_for_booking(date(2026, 7, 16), now_after_close) is False
        assert is_day_open_for_booking(date(2026, 7, 16), now_after_open) is True

    def test_only_weekday_pair_sessions_are_bookable(self, lab_work, room, semester):
        weekday_pair = next_open_weekday_pair(days_ahead=3, hour=10, minute=35)
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

    def test_offset_interval_inside_pair_is_bookable(self):
        offset_start = next_open_weekday_pair(days_ahead=3, hour=11, minute=35)
        assert is_pair_time_for_booking(offset_start) is True

    def test_student_busy_intervals_are_hidden(self, student, student_group, session, semester):
        BookingService().create_booking(student, session.pk)
        discipline_two = Discipline.objects.create(
            title="Гидравлика",
            semester=semester,
            is_published=True,
        )
        student_group.disciplines.add(discipline_two)
        second_lab = create_lab_work(
            discipline_two,
            number=1,
            title="ЛР 2",
            duration_minutes=60,
            is_published=True,
        )
        overlap = LabSession.objects.create(
            lab_work=second_lab,
            room=session.room,
            semester=semester,
            starts_at=session.starts_at,
            ends_at=session.starts_at + timezone.timedelta(minutes=60),
            capacity=2,
            status=LabSessionStatus.OPEN,
        )
        free_start = next_open_weekday_pair(days_ahead=5, hour=10, minute=35)
        free_slot = LabSession.objects.create(
            lab_work=second_lab,
            room=session.room,
            semester=semester,
            starts_at=free_start,
            ends_at=free_start + timezone.timedelta(minutes=60),
            capacity=2,
            status=LabSessionStatus.OPEN,
        )
        qs = bookable_sessions_qs(lab_work_id=second_lab.pk, student=student)
        assert overlap not in qs
        assert free_slot in qs


@pytest.mark.django_db
def test_my_bookings_web_url_reversal():
    from django.urls import reverse

    assert reverse("my-bookings") == "/my-bookings/"


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
    staff.profile.training_center = session.room.training_center
    staff.profile.save(update_fields=["training_center"])
    client = APIClient()
    client.force_authenticate(user=staff)
    response = client.post(
        "/api/v1/admin/bookings/manual/",
        {"student_id": student.pk, "lab_session_id": session.pk},
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_support_message_api(student, staff, room):
    staff.profile.training_center = room.training_center
    staff.profile.save(update_fields=["training_center"])
    ticket = SupportTicket.objects.create(
        student=student,
        subject="Проблема",
        body="Не работает",
        training_center=room.training_center,
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
def test_disciplines_active_semester_only(student, student_group, discipline, inactive_discipline):
    client = Client()
    client.force_login(student)
    response = client.get("/disciplines/")
    assert response.status_code == 200
    assert discipline.title.encode() in response.content
    assert inactive_discipline.title.encode() not in response.content


@pytest.mark.django_db
def test_logout_via_post(student):
    client = Client()
    client.force_login(student)
    response = client.post("/logout/")
    assert response.status_code == 302
    assert response.url.endswith("/login/")
    response = client.get("/disciplines/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_logout_get_not_allowed(student):
    client = Client()
    client.force_login(student)
    response = client.get("/logout/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_book_page_student_only(staff, student_group, lab_work):
    staff.profile.training_center = None
    staff.profile.save(update_fields=["training_center"])
    client = Client()
    client.force_login(staff)
    response = client.get(f"/lab-works/{lab_work.pk}/book/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_staff_bookings_filters_and_manual_web(staff, student, session):
    staff.profile.training_center = session.room.training_center
    staff.profile.save(update_fields=["training_center"])
    session.lab_work.training_centers.add(session.room.training_center)
    client = Client()
    client.force_login(staff)
    response = client.get("/staff/bookings/", {"student": student.email})
    assert response.status_code == 200

    response = client.post(
        "/staff/bookings/manual/",
        {"student_id": student.pk, "session_id": session.pk},
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
    )
    client = Client()
    client.force_login(staff)
    response = client.get("/staff/bookings/")
    assert response.status_code == 200
    assert other_room.number.encode() not in response.content


@pytest.mark.django_db
def test_staff_bookings_sort_by_student(staff, student, session, student_group, db):
    staff.profile.training_center = session.room.training_center
    staff.profile.save(update_fields=["training_center"])
    session.lab_work.training_centers.add(session.room.training_center)

    student.last_name = "Иванов"
    student.first_name = "Иван"
    student.save(update_fields=["last_name", "first_name"])
    student.profile.group_name = "ГР-1"
    student.profile.save(update_fields=["group_name"])

    other = User.objects.create_user(
        email="zzz@stud.spmi.ru",
        password="pass",
        first_name="Пётр",
        last_name="Петров",
        role=UserRole.STUDENT,
    )
    other.profile.group_name = "ГР-2"
    other.profile.training_center = session.room.training_center
    other.profile.save(update_fields=["group_name", "training_center"])

    BookingService(actor=staff).create_booking(student, session.pk, manual=True)

    starts2 = session.starts_at + timezone.timedelta(days=1)
    session2 = LabSession.objects.create(
        lab_work=session.lab_work,
        room=session.room,
        semester=session.semester,
        starts_at=starts2,
        ends_at=starts2 + timezone.timedelta(minutes=90),
        capacity=5,
        status=LabSessionStatus.OPEN,
    )
    BookingService(actor=staff).create_booking(other, session2.pk, manual=True)

    client = Client()
    client.force_login(staff)
    response = client.get("/staff/bookings/", {"sort": "student", "dir": "asc"})
    assert response.status_code == 200
    content = response.content.decode()
    assert content.index("Иванов") < content.index("Петров")

    response = client.get("/staff/bookings/", {"sort": "student", "dir": "desc"})
    content = response.content.decode()
    assert content.index("Петров") < content.index("Иванов")


@pytest.mark.django_db
def test_staff_bookings_sort_links_preserve_filters(staff, student, session):
    staff.profile.training_center = session.room.training_center
    staff.profile.save(update_fields=["training_center"])
    session.lab_work.training_centers.add(session.room.training_center)
    BookingService(actor=staff).create_booking(student, session.pk, manual=True)

    client = Client()
    client.force_login(staff)
    response = client.get(
        "/staff/bookings/",
        {"student": student.email, "sort": "date", "dir": "asc"},
    )
    assert response.status_code == 200
    assert b"sort=date" in response.content
    assert student.email.encode() in response.content


@pytest.mark.django_db
def test_my_bookings_sort_by_date(student, session, discipline, room, semester, student_group):
    discipline2 = Discipline.objects.create(title="Химия", semester=semester, is_published=True)
    student_group.disciplines.add(discipline2)
    lab_work2 = create_lab_work(discipline2, number=2, title="ЛР 2", duration_minutes=90, is_published=True)

    BookingService(actor=student).create_booking(student, session.pk)

    starts2 = session.starts_at + timezone.timedelta(days=2)
    session2 = LabSession.objects.create(
        lab_work=lab_work2,
        room=room,
        semester=semester,
        starts_at=starts2,
        ends_at=starts2 + timezone.timedelta(minutes=90),
        capacity=5,
        status=LabSessionStatus.OPEN,
    )
    BookingService(actor=student).create_booking(student, session2.pk)

    client = Client()
    client.force_login(student)
    response = client.get("/my-bookings/", {"sort": "date", "dir": "asc"})
    assert response.status_code == 200
    content = response.content.decode()
    assert content.index(session.starts_at.strftime("%d.%m.%Y")) < content.index(
        session2.starts_at.strftime("%d.%m.%Y")
    )
