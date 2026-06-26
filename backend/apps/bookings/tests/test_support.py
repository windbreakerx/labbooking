from datetime import datetime

import pytest
from django.utils import timezone

from apps.bookings.models import SupportTicket
from apps.bookings.services.support import add_business_hours, is_support_ticket_overdue


def _local(year, month, day, hour=0, minute=0):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime(year, month, day, hour, minute), tz)


def test_add_business_hours_skips_weekend():
    friday = _local(2026, 6, 26, 10, 0)
    deadline = add_business_hours(friday, 24)
    assert deadline == _local(2026, 6, 29, 10, 0)


def test_add_business_hours_within_single_day():
    monday = _local(2026, 6, 22, 9, 0)
    deadline = add_business_hours(monday, 6)
    assert deadline == _local(2026, 6, 22, 15, 0)


@pytest.mark.django_db
def test_is_support_ticket_overdue_open_ticket(student, room):
    ticket = SupportTicket.objects.create(
        student=student,
        subject="Вопрос",
        body="Текст",
        training_center=room.training_center,
    )
    created = _local(2026, 6, 22, 10, 0)
    SupportTicket.objects.filter(pk=ticket.pk).update(created_at=created)
    ticket.refresh_from_db()

    assert not is_support_ticket_overdue(ticket, now=_local(2026, 6, 22, 20, 0))
    assert is_support_ticket_overdue(ticket, now=_local(2026, 6, 23, 11, 0))


@pytest.mark.django_db
def test_is_support_ticket_overdue_skips_weekend(student, room):
    ticket = SupportTicket.objects.create(
        student=student,
        subject="Вопрос",
        body="Текст",
        training_center=room.training_center,
    )
    created = _local(2026, 6, 26, 10, 0)
    SupportTicket.objects.filter(pk=ticket.pk).update(created_at=created)
    ticket.refresh_from_db()

    assert not is_support_ticket_overdue(ticket, now=_local(2026, 6, 27, 12, 0))
    assert not is_support_ticket_overdue(ticket, now=_local(2026, 6, 29, 9, 0))
    assert is_support_ticket_overdue(ticket, now=_local(2026, 6, 29, 11, 0))


@pytest.mark.django_db
def test_is_support_ticket_overdue_not_for_answered(student, room):
    ticket = SupportTicket.objects.create(
        student=student,
        subject="Вопрос",
        body="Текст",
        training_center=room.training_center,
        status=SupportTicket.Status.ANSWERED,
    )
    created = _local(2026, 6, 1, 10, 0)
    SupportTicket.objects.filter(pk=ticket.pk).update(created_at=created)
    ticket.refresh_from_db()

    assert not is_support_ticket_overdue(ticket, now=_local(2026, 6, 10, 10, 0))
