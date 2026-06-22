---
name: labbooking-pytest-pilot
description: Defines the pytest and manual acceptance gate for labbooking pilot work. Use before finishing features that affect booking, access scope, staff UI, CSV import, reports, scheduling, deployment, or pilot data.
---

# labbooking-pytest-pilot

Use this skill before finishing any feature that affects booking, access scope, staff UI, lab-head UI, CSV import, reports, scheduling, deployment, or pilot data.

## Focused Test Commands

```bash
cd backend
pytest apps/bookings/tests/test_booking.py -v
pytest apps/bookings/tests/test_student_scope.py -v
pytest apps/bookings/tests/test_staff_scope.py -v
pytest apps/bookings/tests/test_manual_booking.py -v
pytest apps/bookings/tests/test_lab_head_ui.py -v
pytest apps/bookings/tests/test_pilot_visibility.py -v
```

## Full Gate

```bash
cd backend
pytest
```

## Checklist

- Add a regression test for every fixed pilot bug.
- Prefer focused tests first, then full test suite before release.
- If a change affects seed or CSV data, run `seed_demo` and `test_pilot_visibility`.
- If a change affects a staff action, test both own-lab and foreign-lab cases.
- If tests cannot be run, document why and list the exact commands to run.

## Manual Acceptance

- Student: login, visible curriculum only, book, cancel, support.
- Staff: own lab bookings, filters, status, manual booking, support, report.
- Lab head: own lab people, bindings, lab works, stands, schedule.
