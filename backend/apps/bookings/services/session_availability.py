from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.bookings.models import BookingStatus
from apps.scheduling.models import Holiday, LabSession, LabSessionStatus


def _parse_opens_at() -> time:
    raw = settings.BOOKING_DAY_OPENS_AT
    hour, minute = raw.split(":")
    return time(int(hour), int(minute))


def day_opens_at(session_date) -> datetime:
    """Момент, когда день session_date становится доступен для записи (22:00 предыдущего дня)."""
    opens_time = _parse_opens_at()
    open_date = session_date - timedelta(days=1)
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(open_date, opens_time), tz)


def is_day_open_for_booking(session_date, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    return now >= day_opens_at(session_date)


def bookable_sessions_qs(lab_work_id: int | None = None) -> QuerySet[LabSession]:
    now = timezone.now()
    horizon = now + timedelta(days=settings.BOOKING_HORIZON_DAYS)
    holiday_dates = set(Holiday.objects.values_list("date", flat=True))

    qs = (
        LabSession.objects.filter(
            status=LabSessionStatus.OPEN,
            starts_at__gt=now,
            starts_at__lte=horizon,
        )
        .select_related("lab_work", "room", "room__training_center")
        .annotate(
            booked_count=Count(
                "bookings",
                filter=Q(bookings__current_status=BookingStatus.BOOKED),
            )
        )
        .order_by("starts_at")
    )
    if lab_work_id:
        qs = qs.filter(lab_work_id=lab_work_id)

    if holiday_dates:
        qs = qs.exclude(starts_at__date__in=holiday_dates)

    open_dates = {d for d in _distinct_session_dates(qs) if is_day_open_for_booking(d, now)}
    if not open_dates:
        return qs.none()
    return qs.filter(starts_at__date__in=open_dates)


def _distinct_session_dates(qs: QuerySet) -> list:
    return list(qs.dates("starts_at", "day"))


def get_session_filter_options(
    lab_work_id: int,
    date: str | None = None,
    time_str: str | None = None,
    tc_number: str | None = None,
) -> dict:
    """Каскадные опции: date → time → training_center → room → sessions."""
    qs = bookable_sessions_qs(lab_work_id=lab_work_id)

    if date:
        qs = qs.filter(starts_at__date=date)
        times = sorted({s.starts_at.strftime("%H:%M") for s in qs})
        if not time_str:
            return {"level": "time", "options": [{"value": t, "label": t} for t in times]}

    if time_str:
        hour, minute = time_str.split(":")
        qs = qs.filter(
            starts_at__hour=int(hour),
            starts_at__minute=int(minute),
        )
        if not tc_number:
            centers = {}
            for s in qs:
                tc = s.room.training_center
                centers[tc.number] = tc
            return {
                "level": "training_center",
                "options": [
                    {"value": str(n), "label": f"УЦ №{n}"}
                    for n in sorted(centers)
                ],
            }

    if tc_number:
        qs = qs.filter(room__training_center__number=int(tc_number))
        rooms = {}
        for s in qs:
            rooms[s.room_id] = s.room
        return {
            "level": "room",
            "options": [
                {"value": str(r.pk), "label": f"ауд. {r.number}"}
                for r in sorted(rooms.values(), key=lambda x: x.number)
            ],
        }

    dates = sorted({s.starts_at.date().isoformat() for s in qs})
    return {
        "level": "date",
        "options": [{"value": d, "label": d} for d in dates],
    }


def get_sessions_for_selection(
    lab_work_id: int,
    date: str,
    time_str: str,
    room_id: int,
) -> QuerySet[LabSession]:
    hour, minute = time_str.split(":")
    return bookable_sessions_qs(lab_work_id=lab_work_id).filter(
        starts_at__date=date,
        starts_at__hour=int(hour),
        starts_at__minute=int(minute),
        room_id=room_id,
    )
