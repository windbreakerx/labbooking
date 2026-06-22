# Pilot acceptance checklist

Use this checklist before opening the pilot to real students and after every production deploy during the pilot.

## Automated checks

Run from the backend container or local backend environment:

```bash
cd backend
pytest apps/bookings/tests/test_booking.py -v
pytest apps/bookings/tests/test_student_scope.py -v
pytest apps/bookings/tests/test_staff_scope.py -v
pytest apps/bookings/tests/test_manual_booking.py -v
pytest apps/bookings/tests/test_lab_head_ui.py -v
pytest apps/bookings/tests/test_pilot_visibility.py -v
pytest
```

On the VM after deploy:

```bash
bash scripts/smoke-test.sh http://127.0.0.1
```

Use the HTTPS domain instead of `http://127.0.0.1` after certificates are enabled.

## Student scenario

- Log in as a student from each pilot group.
- Confirm the student sees only disciplines from their `StudentGroup` curriculum.
- Open a discipline and confirm only allowed lab works are visible.
- Try a direct URL/API id for a foreign discipline or lab work; it must not expose data.
- Select lab work -> date -> pair -> training center -> room -> session.
- Create a booking and confirm it appears in "Мои записи".
- Cancel a booking before the 24-hour deadline.
- Confirm cancellation after the deadline is rejected.
- Create a support ticket only for an available laboratory.

## Staff scenario

- Log in as `LAB_ADMIN`.
- Confirm staff sees only own-lab bookings, sessions, support tickets, people, stands, schedule, and reports.
- Confirm staff without `training_center` sees empty staff data.
- Search bookings by status, discipline, date, and student.
- Change statuses: `VISITED`, `NO_SHOW`, `REACCESS`, `CANCELLED`.
- Search a student by full name, email, and group.
- Manually book the student through the staff calendar.
- Try manual booking into a foreign lab session; it must be denied.
- Reply to a support ticket in the staff lab.
- Download each report and confirm foreign lab rows are absent.

## Lab head scenario

- Log in as `LAB_HEAD`.
- Confirm dashboard opens only when `profile.training_center` is set.
- Add a teacher or lab admin for the same lab.
- Assign disciplines to the person; for pilot this is metadata, not a security boundary.
- Bind and unbind a discipline or lab work to the lab.
- Create a lab work, stand, and schedule entry.
- Confirm foreign lab people, rooms, stands, schedule, bookings, and reports are not visible.

## Email and operations

- Switch `.env` to SMTP and set `EMAIL_FAIL_SILENTLY=0`.
- Send an SMTP test from `manage.py shell`.
- Create booking, cancel booking, mark no-show, mark visited, and grant reaccess; confirm emails arrive or failures appear in logs.
- Run `bash scripts/backup_db.sh` before live pilot and before every risky update.
- Confirm `mark_visited` and `generate_sessions` cron entries are installed if the VM owns those jobs.

## Pilot blockers

- Any cross-group or cross-lab data leak.
- Booking/cancel/status mutation failing on the happy path.
- SMTP silently failing during pilot rehearsal.
- Missing PostgreSQL backup before deploy or data import.
- Staff unable to manually book a student if student self-booking fails.
