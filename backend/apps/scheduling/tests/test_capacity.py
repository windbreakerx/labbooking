import pytest
from datetime import timedelta

from django.utils import timezone

from apps.academics.models import LabWork
from apps.scheduling.models import LabSession, LabSessionStatus, Room, TrainingCenter
from apps.scheduling.services.capacity import lab_session_capacity, sync_open_session_capacities
from apps.scheduling.services.slot_generation import generate_lab_sessions


@pytest.mark.django_db
class TestLabSessionCapacity:
    def test_lab_session_capacity_uses_minimum(self, discipline, semester):
        tc = TrainingCenter.objects.create(number=7)
        room = Room.objects.create(training_center=tc, number="701", capacity=10)
        lab_work = LabWork.objects.create(
            discipline=discipline,
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
        lab_work = LabWork.objects.create(
            discipline=discipline,
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

    def test_sync_open_session_capacities(self, discipline, semester):
        tc = TrainingCenter.objects.create(number=9)
        room = Room.objects.create(training_center=tc, number="901", capacity=10)
        lab_work = LabWork.objects.create(
            discipline=discipline,
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
