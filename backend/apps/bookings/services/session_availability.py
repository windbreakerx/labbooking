from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

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


def day_opens_at(session_date) -> datetime:
    """Момент, когда день session_date становится доступен для записи (22:00 предыдущего дня)."""
    opens_time = _parse_opens_at()
    open_date = session_date - timedelta(days=1)
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(open_date, opens_time), tz)


def is_day_open_for_booking(session_date, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    return now >= day_opens_at(session_date)


def is_weekday_for_booking(session_dt: datetime) -> bool:
    local_dt = timezone.localtime(session_dt)
    return local_dt.weekday() < 5


def is_pair_time_for_booking(session_dt: datetime) -> bool:
    local_dt = timezone.localtime(session_dt)
    starts_at = local_dt.time().replace(second=0, microsecond=0)
    return any(start == starts_at for _, start, _ in UNIVERSITY_PAIR_SLOTS)


def pair_meta_by_time(time_str: str) -> tuple[int, str] | None:
    for number, start, end in UNIVERSITY_PAIR_SLOTS:
        value = f"{start.hour:02d}:{start.minute:02d}"
        if value == time_str:
            return number, f"{number} пара ({value}-{end.hour:02d}:{end.minute:02d})"
    return None


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
        .order_by("starts_at")
    )
    if lab_work_id:
        qs = qs.filter(lab_work_id=lab_work_id)

    if holiday_dates:
        qs = qs.exclude(starts_at__date__in=holiday_dates)

    return _filter_sessions_with_free_seats(qs)


def get_session_filter_options(
    lab_work_id: int,
    date: str | None = None,
    time_str: str | None = None,
    tc_number: str | None = None,
) -> dict:
    """Каскадные опции: date → time → training_center → room → sessions."""
    qs = bookable_sessions_qs(lab_work_id=lab_work_id)

    if date:
        qs = _filter_by_local_date(qs, date)
        times = sorted(
            {timezone.localtime(s.starts_at).strftime("%H:%M") for s in qs},
            key=lambda t: PAIR_ORDER_BY_START.get(t, 99),
        )
        if not time_str:
            options = []
            for t in times:
                meta = pair_meta_by_time(t)
                if meta:
                    _, label = meta
                    options.append({"value": t, "label": label})
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

    date_pairs = {}
    for session in qs:
        local_starts = timezone.localtime(session.starts_at)
        date_key = local_starts.date().isoformat()
        pair_key = local_starts.strftime("%H:%M")
        pair_num = PAIR_ORDER_BY_START.get(pair_key)
        date_pairs.setdefault(date_key, set())
        if pair_num:
            date_pairs[date_key].add(pair_num)
    dates = sorted(date_pairs.keys())
    return {
        "level": "date",
        "options": [
            {
                "value": d,
                "label": (
                    f"{d[8:10]}.{d[5:7]}.{d[0:4]} "
                    f"({WEEKDAY_LABELS[datetime.fromisoformat(d).weekday()]})"
                    f" — пары: {', '.join(str(n) for n in sorted(date_pairs[d]))}"
                ),
            }
            for d in dates
        ],
    }


def get_sessions_for_selection(
    lab_work_id: int,
    date: str,
    time_str: str,
    room_id: int,
) -> QuerySet[LabSession]:
    qs = bookable_sessions_qs(lab_work_id=lab_work_id).filter(room_id=room_id)
    qs = _filter_by_local_date(qs, date)
    qs = _filter_by_local_time(qs, time_str)
    return qs
