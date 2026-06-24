from datetime import datetime, time, timedelta
from functools import lru_cache

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from apps.academics.models import ALLOWED_LAB_DURATIONS
from apps.scheduling.models import Holiday, LabSession, LabSessionStatus

UNIVERSITY_PAIR_SLOTS = [
    (1, time(8, 50), time(10, 20)),
    (2, time(10, 35), time(12, 5)),
    (3, time(12, 35), time(14, 5)),
    (4, time(14, 15), time(15, 45)),
    (5, time(15, 55), time(17, 20)),
    (6, time(17, 30), time(19, 0)),
]
PAIR_ORDER_BY_START = {f"{start.hour:02d}:{start.minute:02d}": number for number, start, _ in UNIVERSITY_PAIR_SLOTS}
WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _parse_opens_at() -> time:
    raw = settings.BOOKING_DAY_OPENS_AT
    hour, minute = raw.split(":")
    return time(int(hour), int(minute))


def _parse_closes_at() -> time:
    raw = settings.BOOKING_DAY_CLOSES_AT
    hour, minute = raw.split(":")
    return time(int(hour), int(minute))


def booking_date_window(now: datetime | None = None) -> tuple:
    """
    Рабочее окно дат записи.
    - До 15:00: [завтра .. +14 дней]
    - 15:00–21:59: [послезавтра .. +14 дней]
    - С 22:00: [послезавтра .. +15 дней]
    """
    local_now = timezone.localtime(now or timezone.now())
    current_date = local_now.date()
    local_time = local_now.time().replace(second=0, microsecond=0)

    min_date = current_date + timedelta(days=1)
    max_date = current_date + timedelta(days=settings.BOOKING_HORIZON_DAYS)

    if local_time >= _parse_closes_at():
        min_date += timedelta(days=1)
    if local_time >= _parse_opens_at():
        max_date += timedelta(days=1)
    return min_date, max_date


def max_bookable_session_date(now: datetime | None = None):
    _, max_date = booking_date_window(now)
    return max_date


def is_day_open_for_booking(session_date, now: datetime | None = None) -> bool:
    min_date, max_date = booking_date_window(now)
    return min_date <= session_date <= max_date


def is_weekday_for_booking(session_dt: datetime) -> bool:
    local_dt = timezone.localtime(session_dt)
    return local_dt.weekday() < 5


def _minutes_between(start: time, end: time) -> int:
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    return end_minutes - start_minutes


@lru_cache(maxsize=None)
def _reachable_sums(max_minutes: int) -> set[int]:
    reachable = {0}
    changed = True
    while changed:
        changed = False
        snapshot = tuple(reachable)
        for value in snapshot:
            for duration in ALLOWED_LAB_DURATIONS:
                candidate = value + duration
                if candidate <= max_minutes and candidate not in reachable:
                    reachable.add(candidate)
                    changed = True
    return reachable


@lru_cache(maxsize=None)
def _pair_start_offsets(pair_minutes: int) -> tuple[int, ...]:
    reachable = _reachable_sums(pair_minutes)
    offsets = sorted(
        offset
        for offset in reachable
        if any(offset + duration <= pair_minutes for duration in ALLOWED_LAB_DURATIONS)
    )
    return tuple(offsets)


def _pair_slot_for_time(moment: time) -> tuple[int, time, time] | None:
    minute_value = moment.hour * 60 + moment.minute
    for number, pair_start, pair_end in UNIVERSITY_PAIR_SLOTS:
        pair_start_minutes = pair_start.hour * 60 + pair_start.minute
        pair_end_minutes = pair_end.hour * 60 + pair_end.minute
        if pair_start_minutes <= minute_value < pair_end_minutes:
            return number, pair_start, pair_end
    return None


def is_pair_time_for_booking(session_dt: datetime) -> bool:
    local_dt = timezone.localtime(session_dt)
    starts_at = local_dt.time().replace(second=0, microsecond=0)
    slot = _pair_slot_for_time(starts_at)
    if not slot:
        return False
    _, pair_start, pair_end = slot
    pair_minutes = _minutes_between(pair_start, pair_end)
    start_minutes = starts_at.hour * 60 + starts_at.minute
    pair_start_minutes = pair_start.hour * 60 + pair_start.minute
    offset = start_minutes - pair_start_minutes
    return offset in _pair_start_offsets(pair_minutes)


def pair_meta_by_time(time_str: str) -> tuple[int, str] | None:
    try:
        starts_at = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return None
    slot = _pair_slot_for_time(starts_at)
    if not slot:
        return None
    number, pair_start, pair_end = slot
    start_value = f"{starts_at.hour:02d}:{starts_at.minute:02d}"
    pair_start_value = f"{pair_start.hour:02d}:{pair_start.minute:02d}"
    pair_end_value = f"{pair_end.hour:02d}:{pair_end.minute:02d}"
    if start_value == pair_start_value:
        return number, f"{number} пара ({pair_start_value}-{pair_end_value})"
    return number, f"{number} пара ({start_value}, окно {pair_start_value}-{pair_end_value})"


def session_interval_label(session: LabSession) -> str:
    local_start = timezone.localtime(session.starts_at)
    local_end = timezone.localtime(session.ends_at)
    start_value = local_start.strftime("%H:%M")
    end_value = local_end.strftime("%H:%M")
    pair_info = pair_meta_by_time(start_value)
    if not pair_info:
        return f"{start_value}-{end_value}"
    pair_number, _ = pair_info
    return f"{start_value}-{end_value} ({pair_number} пара)"


def pair_start_times_for_duration(duration_minutes: int) -> list[time]:
    starts: list[time] = []
    for _, pair_start, pair_end in UNIVERSITY_PAIR_SLOTS:
        pair_minutes = _minutes_between(pair_start, pair_end)
        for offset in _pair_start_offsets(pair_minutes):
            if offset + duration_minutes > pair_minutes:
                continue
            total_minutes = pair_start.hour * 60 + pair_start.minute + offset
            starts.append(time(total_minutes // 60, total_minutes % 60))
    return starts


def _filter_sessions_with_free_seats(qs: QuerySet[LabSession]) -> QuerySet[LabSession]:
    now = timezone.now()
    session_ids = []
    for session in qs:
        local_date = timezone.localtime(session.starts_at).date()
        if not is_weekday_for_booking(session.starts_at):
            continue
        if not is_pair_time_for_booking(session.starts_at):
            continue
        if not is_day_open_for_booking(local_date, now):
            continue
        if session.available_seats <= 0:
            continue
        session_ids.append(session.pk)
    if not session_ids:
        return qs.none()
    return qs.filter(pk__in=session_ids).order_by("starts_at")


def _filter_by_local_date(qs: QuerySet[LabSession], date_iso: str) -> QuerySet[LabSession]:
    session_ids = [
        session.pk
        for session in qs
        if timezone.localtime(session.starts_at).date().isoformat() == date_iso
    ]
    if not session_ids:
        return qs.none()
    return qs.filter(pk__in=session_ids)


def _filter_by_local_time(qs: QuerySet[LabSession], time_str: str) -> QuerySet[LabSession]:
    session_ids = [
        session.pk
        for session in qs
        if timezone.localtime(session.starts_at).strftime("%H:%M") == time_str
    ]
    if not session_ids:
        return qs.none()
    return qs.filter(pk__in=session_ids)


def bookable_sessions_qs(lab_work_id: int | None = None, *, student=None) -> QuerySet[LabSession]:
    now = timezone.now()
    min_date, max_date = booking_date_window(now)
    holiday_dates = set(Holiday.objects.values_list("date", flat=True))

    qs = (
        LabSession.objects.filter(
            status=LabSessionStatus.OPEN,
            starts_at__gt=now,
            starts_at__date__gte=min_date,
            starts_at__date__lte=max_date,
        )
        .select_related("lab_work", "room", "room__training_center")
        .order_by("starts_at")
    )
    if lab_work_id:
        qs = qs.filter(lab_work_id=lab_work_id)

    if holiday_dates:
        qs = qs.exclude(starts_at__date__in=holiday_dates)

    qs = _filter_sessions_with_free_seats(qs)
    if student is not None:
        from apps.bookings.models import BookingStatus

        busy_bookings = student.bookings.filter(current_status=BookingStatus.BOOKED).select_related("lab_session")
        busy_intervals = [
            (booking.lab_session.starts_at, booking.lab_session.ends_at)
            for booking in busy_bookings
        ]
        if busy_intervals:
            session_ids = []
            for session in qs:
                if any(start < session.ends_at and end > session.starts_at for start, end in busy_intervals):
                    continue
                session_ids.append(session.pk)
            qs = qs.filter(pk__in=session_ids) if session_ids else qs.none()
    return qs


def staff_manual_sessions_qs(lab_work_id: int) -> QuerySet[LabSession]:
    """
    Слоты для ручной записи сотрудником: без горизонта записи и фильтра по свободным местам,
    но с ограничениями расписания (будни, пары, праздники, только будущие OPEN-слоты).
    """
    now = timezone.now()
    holiday_dates = set(Holiday.objects.values_list("date", flat=True))
    qs = (
        LabSession.objects.filter(
            status=LabSessionStatus.OPEN,
            starts_at__gt=now,
            lab_work_id=lab_work_id,
        )
        .select_related("lab_work", "room", "room__training_center")
        .order_by("starts_at")
    )
    if holiday_dates:
        qs = qs.exclude(starts_at__date__in=holiday_dates)

    session_ids = []
    for session in qs:
        if not is_weekday_for_booking(session.starts_at):
            continue
        if not is_pair_time_for_booking(session.starts_at):
            continue
        session_ids.append(session.pk)
    if not session_ids:
        return qs.none()
    return qs.filter(pk__in=session_ids)


def get_session_filter_options(
    lab_work_id: int,
    date: str | None = None,
    time_str: str | None = None,
    tc_number: str | None = None,
    *,
    sessions_qs: QuerySet[LabSession] | None = None,
) -> dict:
    """Каскадные опции: date → time → training_center → room → sessions."""
    qs = sessions_qs if sessions_qs is not None else bookable_sessions_qs(lab_work_id=lab_work_id)

    if date:
        qs = _filter_by_local_date(qs, date)
        sessions_by_start = {
            timezone.localtime(session.starts_at).strftime("%H:%M"): session for session in qs
        }
        times = sorted(sessions_by_start.keys(), key=lambda t: t)
        if not time_str:
            options = []
            for t in times:
                options.append({"value": t, "label": session_interval_label(sessions_by_start[t])})
            return {"level": "time", "options": options}

    if time_str:
        qs = _filter_by_local_time(qs, time_str)
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

    date_meta = {}
    for session in qs:
        local_starts = timezone.localtime(session.starts_at)
        date_key = local_starts.date().isoformat()
        pair_key = local_starts.strftime("%H:%M")
        pair_info = pair_meta_by_time(pair_key)
        pair_num = pair_info[0] if pair_info else None
        if date_key not in date_meta:
            date_meta[date_key] = {"pairs": set(), "available_seats": 0}
        if pair_num:
            date_meta[date_key]["pairs"].add(pair_num)
        date_meta[date_key]["available_seats"] += session.available_seats
    dates = sorted(date_meta.keys())
    return {
        "level": "date",
        "options": [
            {
                "value": d,
                "label": (
                    f"{d[8:10]}.{d[5:7]}.{d[0:4]} "
                    f"({WEEKDAY_LABELS[datetime.fromisoformat(d).weekday()]})"
                    f" — пары: {', '.join(str(n) for n in sorted(date_meta[d]['pairs']))}"
                ),
                "available_seats": date_meta[d]["available_seats"],
            }
            for d in dates
        ],
    }


def get_sessions_for_date_time(
    lab_work_id: int,
    date: str,
    time_str: str,
    *,
    sessions_qs: QuerySet[LabSession] | None = None,
) -> QuerySet[LabSession]:
    qs = sessions_qs if sessions_qs is not None else bookable_sessions_qs(lab_work_id=lab_work_id)
    qs = _filter_by_local_date(qs, date)
    qs = _filter_by_local_time(qs, time_str)
    return qs


def get_sessions_for_selection(
    lab_work_id: int,
    date: str,
    time_str: str,
    room_id: int,
    *,
    sessions_qs: QuerySet[LabSession] | None = None,
) -> QuerySet[LabSession]:
    return get_sessions_for_date_time(
        lab_work_id,
        date,
        time_str,
        sessions_qs=sessions_qs,
    ).filter(room_id=room_id)
