# labbooking-booking-service

Use this skill when changing booking, cancellation, statuses, waitlist, capacity, manual booking, booking windows, or any rule that decides whether a student can book a lab session.

## Source Of Truth

- Keep booking business rules in `backend/apps/bookings/services/booking.py`.
- Keep slot visibility and cascade filter rules in `backend/apps/bookings/services/session_availability.py`.
- Views, serializers, templates, and API endpoints may validate request shape and permissions, but must delegate booking mutations to `BookingService`.

## Checklist

- Do not duplicate booking rules in DRF serializers or Django views.
- Preserve audit logging for booking creation, cancellation, status changes, waitlist and session cancellation.
- Preserve email side effects and make SMTP failures observable in pilot/prod logs.
- Keep manual staff booking explicit with `manual=True` and `skip_student_rules=True`; never use that path for student self-booking.
- Re-check room overlap capacity whenever changing `LabSession.available_seats` or `BookingService._room_overlap_booked`.

## Commands

```bash
cd backend
pytest apps/bookings/tests/test_booking.py -v
pytest apps/bookings/tests/test_manual_booking.py -v
```

## Manual Scenarios

- Student books a visible lab work in the allowed window.
- Student cannot book a foreign group lab work.
- Student cannot cancel after the 24-hour deadline.
- Staff can manually book a student into an allowed lab session.
- Room capacity blocks parallel sessions in the same room.
