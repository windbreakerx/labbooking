import pytest
from datetime import datetime, time, timedelta

from django.test import Client
from django.utils import timezone

from apps.bookings.tests.conftest import create_lab_work
from apps.academics.models import Discipline
from apps.bookings.services import BookingError, BookingService, search_students_for_staff
from apps.bookings.services.session_availability import (
    bookable_sessions_qs,
    is_manual_session_time_allowed,
    is_session_on_current_pair,
    manual_booking_max_date,
    staff_manual_sessions_qs,
)
from apps.scheduling.models import Holiday, LabSession, LabSessionStatus, LabStand, Room, TrainingCenter
from apps.users.models import User, UserRole


def _link_lab_to_tc(lab_work, room):
    lab_work.training_centers.add(room.training_center)


@pytest.mark.django_db
class TestSearchStudentsForStaff:
    def test_search_by_email(self, student):
        results = list(search_students_for_staff("s@stud"))
        assert student in results

    def test_search_by_group_name(self, student, student_group):
        student.profile.group_name = student_group.name
        student.profile.save(update_fields=["group_name"])
        results = list(search_students_for_staff("TEST-24"))
        assert student in results

    def test_search_by_full_name(self, student):
        results = list(search_students_for_staff("B A"))
        assert student in results

    def test_short_query_returns_empty(self):
        assert not search_students_for_staff(" ").exists()


@pytest.mark.django_db
class TestStaffManualSessions:
    def test_excludes_session_beyond_manual_horizon(
        self,
        lab_work,
        far_session,
        session,
    ):
        manual_ids = set(staff_manual_sessions_qs(lab_work.pk).values_list("pk", flat=True))
        student_ids = set(bookable_sessions_qs(lab_work_id=lab_work.pk).values_list("pk", flat=True))
        assert far_session.pk not in manual_ids
        assert session.pk in manual_ids
        assert far_session.pk not in student_ids

    def test_excludes_past_session(self, lab_work, room, semester):
        past_start = timezone.now() - timedelta(days=1)
        past_start = past_start.replace(hour=10, minute=35, second=0, microsecond=0)
        past_session = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=past_start,
            ends_at=past_start + timedelta(minutes=90),
            capacity=2,
            status=LabSessionStatus.OPEN,
        )
        manual_ids = set(staff_manual_sessions_qs(lab_work.pk).values_list("pk", flat=True))
        assert past_session.pk not in manual_ids

    def test_includes_current_pair_session(self, lab_work, room, semester, monkeypatch):
        tz = timezone.get_current_timezone()
        fixed_now = timezone.make_aware(datetime(2026, 6, 10, 13, 7), tz)  # среда
        monkeypatch.setattr(timezone, "now", lambda: fixed_now)
        pair_start = timezone.make_aware(datetime(2026, 6, 10, 12, 35), tz)
        current_pair_session = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=pair_start,
            ends_at=pair_start + timedelta(minutes=90),
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        assert is_session_on_current_pair(current_pair_session.starts_at, fixed_now)
        assert is_manual_session_time_allowed(current_pair_session, fixed_now)
        manual_ids = set(staff_manual_sessions_qs(lab_work.pk).values_list("pk", flat=True))
        assert current_pair_session.pk in manual_ids


@pytest.mark.django_db
class TestStaffManualBookingWeb:
    def test_student_search_endpoint(self, staff, student, session):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(session.lab_work, session.room)
        client = Client()
        client.force_login(staff)
        response = client.get("/staff/bookings/manual/search/", {"q": "B A"})
        assert response.status_code == 200
        assert student.email.encode() in response.content

    def test_manual_filter_foreign_lab_work_denied(
        self,
        staff,
        session,
        lab_work,
        discipline,
        semester,
    ):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(lab_work, session.room)
        other_tc = TrainingCenter.objects.create(number=99)
        foreign_lab = create_lab_work(
            discipline,
            number=2,
            title="Чужая ЛР",
            duration_minutes=90,
            is_published=True,
        )
        foreign_lab.training_centers.add(other_tc)
        client = Client()
        client.force_login(staff)
        response = client.get(f"/staff/bookings/manual/filter/{foreign_lab.pk}/")
        assert response.status_code == 404

    def test_manual_booking_by_student_id(self, staff, student, session):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(session.lab_work, session.room)
        client = Client()
        client.force_login(staff)
        response = client.post(
            "/staff/bookings/manual/",
            {"student_id": student.pk, "session_id": session.pk},
        )
        assert response.status_code == 302
        assert student.bookings.filter(lab_session=session, registration_type="MANUAL").exists()

    def test_manual_booking_foreign_session_denied(self, staff, student, session, room):
        staff.profile.training_center = room.training_center
        staff.profile.save(update_fields=["training_center"])
        other_tc = TrainingCenter.objects.create(number=88)
        other_room = Room.objects.create(training_center=other_tc, number="888", capacity=5)
        foreign_session = LabSession.objects.create(
            lab_work=session.lab_work,
            room=other_room,
            semester=session.semester,
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        client = Client()
        client.force_login(staff)
        response = client.post(
            "/staff/bookings/manual/",
            {"student_id": student.pk, "session_id": foreign_session.pk},
        )
        assert response.status_code == 302
        assert not student.bookings.filter(lab_session=foreign_session).exists()

    def test_manual_booking_bypasses_room_capacity(
        self,
        staff,
        student,
        session,
        lab_work,
        discipline,
        room,
        semester,
        student_group,
    ):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(lab_work, session.room)
        room.capacity = 1
        room.save(update_fields=["capacity"])

        other = User.objects.create_user(
            email="other-manual@stud.spmi.ru",
            password="pass",
            first_name="O",
            last_name="T",
            role=UserRole.STUDENT,
        )
        other.profile.student_group = student_group
        other.profile.save(update_fields=["student_group"])

        second_lab = create_lab_work(
            discipline,
            number=2,
            title="ЛР 2",
            duration_minutes=90,
            capacity=5,
            is_published=True,
        )
        second_lab.training_centers.add(room.training_center)
        parallel_session = LabSession.objects.create(
            lab_work=second_lab,
            room=room,
            semester=semester,
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        BookingService(actor=staff).create_booking(
            other,
            session.pk,
            manual=True,
        )
        client = Client()
        client.force_login(staff)
        response = client.post(
            "/staff/bookings/manual/",
            {"student_id": student.pk, "session_id": parallel_session.pk},
        )
        assert response.status_code == 302
        assert student.bookings.filter(lab_session=parallel_session).exists()


@pytest.mark.django_db
class TestManualBookingRules:
    def test_manual_rejects_lab_work_outside_student_curriculum(
        self,
        staff,
        student,
        session,
        discipline,
        semester,
    ):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(session.lab_work, session.room)
        other_discipline = Discipline.objects.create(
            title="Не в учебном плане",
            semester=semester,
            is_published=True,
        )
        foreign_lab = create_lab_work(
            other_discipline,
            number=99,
            title="Чужая ЛР",
            duration_minutes=90,
            is_published=True,
        )
        foreign_lab.training_centers.add(session.room.training_center)
        foreign_session = LabSession.objects.create(
            lab_work=foreign_lab,
            room=session.room,
            semester=semester,
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        service = BookingService(actor=staff)
        with pytest.raises(BookingError, match="недоступна для вашей группы"):
            service.create_booking(student, foreign_session.pk, manual=True)

    def test_manual_rejects_stand_blocked_session(
        self,
        staff,
        student,
        session,
        room,
        semester,
        student_group,
    ):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(session.lab_work, session.room)
        stand = LabStand.objects.create(
            name="Общий стенд",
            inventory_number="MAN-ST-1",
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
            number=2,
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
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        BookingService().create_booking(student, session.pk)
        service = BookingService(actor=staff)
        with pytest.raises(BookingError, match="Стенд уже занят"):
            service.create_booking(student, second_session.pk, manual=True)

    def test_manual_overlap_returns_warning_not_error(
        self,
        staff,
        student,
        session,
        lab_work,
        room,
        semester,
    ):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(lab_work, session.room)
        session2 = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        BookingService().create_booking(student, session.pk)
        service = BookingService(actor=staff)
        booking = service.create_booking(student, session2.pk, manual=True)
        assert booking.registration_type == "MANUAL"
        assert len(service.booking_warnings) == 1
        assert "пересекающееся время" in service.booking_warnings[0]

    def test_manual_skips_discipline_limit(
        self,
        staff,
        student,
        session,
        lab_work,
        room,
        semester,
    ):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(lab_work, session.room)
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
        booking = BookingService(actor=staff).create_booking(student, session2.pk, manual=True)
        assert booking.registration_type == "MANUAL"

    def test_manual_rejects_holiday_session(self, staff, student, session, lab_work, room, semester):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(lab_work, session.room)
        holiday_date = timezone.localtime(session.starts_at).date()
        Holiday.objects.create(date=holiday_date, name="Праздник")
        service = BookingService(actor=staff)
        with pytest.raises(BookingError, match="праздничный"):
            service.create_booking(student, session.pk, manual=True)

    def test_manual_rejects_session_beyond_two_working_weeks(
        self,
        staff,
        student,
        far_session,
        session,
    ):
        staff.profile.training_center = session.room.training_center
        staff.profile.save(update_fields=["training_center"])
        _link_lab_to_tc(session.lab_work, session.room)
        service = BookingService(actor=staff)
        with pytest.raises(BookingError, match="рабочие недели"):
            service.create_booking(student, far_session.pk, manual=True)

    def test_manual_booking_max_date_counts_working_days(self):
        tz = timezone.get_current_timezone()
        monday = timezone.make_aware(datetime(2026, 6, 8), tz).date()  # понедельник
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(timezone, "now", lambda: timezone.make_aware(datetime(2026, 6, 8, 10, 0), tz))
            assert manual_booking_max_date() == monday + timedelta(days=14)  # 10 рабочих дней
