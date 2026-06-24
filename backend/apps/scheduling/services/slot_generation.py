"""Генерация слотов LabSession по лабораторным работам и аудиториям."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from apps.academics.models import ALLOWED_LAB_DURATIONS, LabWork, Semester
from apps.bookings.services.session_availability import pair_start_times_for_duration
from apps.scheduling.models import Holiday, LabSession, LabSessionStatus
from apps.scheduling.services.capacity import lab_session_capacity

EXCLUDED_ROOM_NUMBERS = {"2116"}


def generate_lab_sessions(
    *,
    semester: Semester,
    weeks: int | None = None,
    now: datetime | None = None,
) -> int:
    """
    Для каждой опубликованной ЛР с default_room создаёт интервальные слоты
    внутри университетских пар на все будние дни в пределах горизонта записи.
    """
    local_now = timezone.localtime(now or timezone.now())
    today = local_now.date()
    days_ahead = max((weeks or 2) * 7, settings.BOOKING_HORIZON_DAYS + 1)
    tz = timezone.get_current_timezone()

    lab_works = (
        LabWork.objects.filter(
            is_published=True,
            default_room__isnull=False,
        )
        .exclude(default_room__number__in=EXCLUDED_ROOM_NUMBERS)
        .select_related("default_room")
    )

    holidays = set(Holiday.objects.values_list("date", flat=True))
    starts_by_duration = {
        duration: set(pair_start_times_for_duration(duration)) for duration in ALLOWED_LAB_DURATIONS
    }
    created = 0

    for day_offset in range(1, days_ahead + 1):
        session_date = today + timedelta(days=day_offset)
        if session_date.weekday() >= 5 or session_date in holidays:
            continue

        for start_time in sorted(starts_by_duration[30]):
            starts_at = timezone.make_aware(datetime.combine(session_date, start_time), tz)
            if starts_at <= local_now:
                continue

            for lab_work in lab_works:
                room = lab_work.default_room
                if start_time not in starts_by_duration.get(lab_work.duration_minutes, set()):
                    continue
                ends_at = starts_at + timedelta(minutes=lab_work.duration_minutes)
                _, was_created = LabSession.objects.update_or_create(
                    lab_work=lab_work,
                    room=room,
                    semester=semester,
                    starts_at=starts_at,
                    defaults={
                        "ends_at": ends_at,
                        "capacity": lab_session_capacity(lab_work, room),
                        "status": LabSessionStatus.OPEN,
                    },
                )
                if was_created:
                    created += 1

    return created
