"""Расчёт вместимости слотов лабораторных работ."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.academics.models import LabWork
from apps.scheduling.models import LabSession, LabSessionStatus, Room


def lab_session_capacity(lab_work: LabWork, room: Room) -> int:
    return min(lab_work.capacity, room.capacity)


def sync_open_session_capacities(lab_work: LabWork) -> int:
    """Обновляет capacity у будущих открытых слотов после изменения lab_work.capacity."""
    updated = 0
    now = timezone.now()
    sessions = LabSession.objects.filter(
        lab_work=lab_work,
        starts_at__gt=now,
        status=LabSessionStatus.OPEN,
    ).select_related("room")
    for session in sessions:
        new_capacity = lab_session_capacity(lab_work, session.room)
        if session.capacity != new_capacity:
            session.capacity = new_capacity
            session.save(update_fields=["capacity"])
            updated += 1
    return updated


def sync_open_session_durations(lab_work: LabWork) -> int:
    """Обновляет ends_at у будущих открытых слотов без записей."""
    updated = 0
    now = timezone.now()
    sessions = (
        LabSession.objects.filter(
            lab_work=lab_work,
            starts_at__gt=now,
            status=LabSessionStatus.OPEN,
        )
        .annotate(bookings_count=Count("bookings"))
        .filter(bookings_count=0)
    )
    for session in sessions:
        new_ends_at = session.starts_at + timedelta(minutes=lab_work.duration_minutes)
        if session.ends_at != new_ends_at:
            session.ends_at = new_ends_at
            session.save(update_fields=["ends_at"])
            updated += 1
    return updated
