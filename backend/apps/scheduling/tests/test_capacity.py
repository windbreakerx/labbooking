import pytest
from datetime import timedelta

from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.tests.conftest import create_lab_work
from apps.scheduling.models import LabSession, LabSessionStatus, Room, TrainingCenter
from apps.users.models import User, UserRole
from apps.scheduling.services.capacity import (
    lab_session_capacity,
    sync_open_session_capacities,
    sync_open_session_durations,
)
from apps.scheduling.services.slot_generation import generate_lab_sessions


@pytest.mark.django_db
class TestLabSessionCapacity:
    def test_lab_session_capacity_uses_minimum(self, discipline, semester):
        tc = TrainingCenter.objects.create(number=7)
        room = Room.objects.create(training_center=tc, number="701", capacity=10)
        lab_work = create_lab_work(
            discipline,
            number=1,
            title="ЛР с лимитом",
            duration_minutes=90,
            capacity=3,
            is_published=True,
            default_room=room,
        )
        assert lab_session_capacity(lab_work, room) == 3

    def test_generate_sessions_uses_lab_work_capacity(self, discipline, semester):
        tc = TrainingCenter.objects.create(number=8)
        room = Room.objects.create(training_center=tc, number="801", capacity=10)
        lab_work = create_lab_work(
            discipline,
            number=1,
            title="ЛР для генерации",
            duration_minutes=90,
            capacity=3,
            is_published=True,
            default_room=room,
        )
        generate_lab_sessions(semester=semester, weeks=2)
        session = LabSession.objects.filter(lab_work=lab_work).first()
        assert session is not None
        assert session.capacity == 3

    def test_generate_sessions_creates_interval_starts(self, discipline, semester):
        tc = TrainingCenter.objects.create(number=18)
        room = Room.objects.create(training_center=tc, number="1801", capacity=10)
        lab_work = create_lab_work(
            discipline,
            number=3,
            title="ЛР 60 минут",
            duration_minutes=60,
            capacity=3,
            is_published=True,
            default_room=room,
        )
        generate_lab_sessions(semester=semester, weeks=1)
        starts = {
            timezone.localtime(start).strftime("%H:%M")
            for start in LabSession.objects.filter(lab_work=lab_work).values_list("starts_at", flat=True)
        }
        assert "10:35" in starts
        assert "11:05" in starts

    def test_sync_open_session_capacities(self, discipline, semester):
        tc = TrainingCenter.objects.create(number=9)
        room = Room.objects.create(training_center=tc, number="901", capacity=10)
        lab_work = create_lab_work(
            discipline,
            number=1,
            title="ЛР для синхронизации",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        starts = timezone.now() + timedelta(days=3)
        session = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=starts,
            ends_at=starts + timedelta(minutes=90),
            capacity=10,
            status=LabSessionStatus.OPEN,
        )
        lab_work.capacity = 3
        lab_work.save(update_fields=["capacity"])
        sync_open_session_capacities(lab_work)
        session.refresh_from_db()
        assert session.capacity == 3

    def test_sync_open_session_durations_updates_only_sessions_without_bookings(self, discipline, semester):
        tc = TrainingCenter.objects.create(number=10)
        room = Room.objects.create(training_center=tc, number="1001", capacity=10)
        lab_work = create_lab_work(
            discipline,
            number=2,
            title="ЛР для синхронизации длительности",
            duration_minutes=90,
            capacity=5,
            is_published=True,
        )
        starts = timezone.now() + timedelta(days=3)
        free_session = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=starts,
            ends_at=starts + timedelta(minutes=90),
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        booked_session = LabSession.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=starts + timedelta(days=1),
            ends_at=starts + timedelta(days=1, minutes=90),
            capacity=5,
            status=LabSessionStatus.OPEN,
        )
        student = User.objects.create_user(
            email="duration-sync-student@spmi.ru",
            password="pass",
            first_name="Dur",
            last_name="Sync",
            role=UserRole.STUDENT,
        )
        Booking.objects.create(
            student=student,
            lab_session=booked_session,
            lab_work=lab_work,
            discipline=discipline,
            room=room,
            scheduled_at=booked_session.starts_at,
        )

        lab_work.duration_minutes = 60
        lab_work.save(update_fields=["duration_minutes"])

        updated_count = sync_open_session_durations(lab_work)
        free_session.refresh_from_db()
        booked_session.refresh_from_db()

        assert updated_count == 1
        assert free_session.ends_at == free_session.starts_at + timedelta(minutes=60)
        assert booked_session.ends_at == booked_session.starts_at + timedelta(minutes=90)
