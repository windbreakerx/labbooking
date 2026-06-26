from datetime import datetime, timedelta

from django.utils import timezone


def _skip_to_next_weekday(dt: datetime) -> datetime:
    while dt.weekday() >= 5:
        dt = (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return dt


def add_business_hours(start: datetime, hours: int) -> datetime:
    """Add weekday-only hours; Saturday and Sunday are skipped entirely."""
    current = timezone.localtime(start)
    remaining = timedelta(hours=hours)
    while remaining > timedelta(0):
        current = _skip_to_next_weekday(current)
        day_end = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        chunk = min(remaining, day_end - current)
        current += chunk
        remaining -= chunk
    return current


def is_support_ticket_overdue(ticket, *, now: datetime | None = None) -> bool:
    from apps.bookings.models import SupportTicket

    if ticket.status != SupportTicket.Status.OPEN:
        return False
    now = now or timezone.now()
    deadline = add_business_hours(ticket.created_at, 24)
    return timezone.localtime(now) > deadline
