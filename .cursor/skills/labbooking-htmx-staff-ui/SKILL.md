---
name: labbooking-htmx-staff-ui
description: Staff and lab-head web UI in labbooking — bookings table, manual booking, support replies, filters, CRUD forms, calendar selection for operators. Simple tables over fancy UI. Use when changing staff/*, lab_head/*, staff_bookings.html, or staff HTMX partials.
---

# labbooking-htmx-staff-ui

Use for staff and lab-head pages: `staff_bookings.html`, `staff/*`, `lab_head/*`, staff support/reports, manual booking dialog.

For HTMX mechanics (partials, `hx-*`, `afterSwap`, shared filter partials): **`labbooking-htmx-patterns`**.

For scoping: **`labbooking-access-scope`**. For booking rules: **`labbooking-booking-service`**.

## Philosophy

- Tables and forms first; cards only when they speed up an operator task.
- HTMX where it saves clicks (student search, manual booking cascade, inline status) — not everywhere.
- `<dialog>` + vanilla JS for modals (see `staff_bookings.html` manual booking).
- `details.row-actions` for per-row actions in tables.

## UI boundaries

- Keep business decisions in services/querysets, not templates.
- HTMX partials render small, replaceable fragments from server-side state.
- Staff and lab-head pages must use scoped querysets before rendering data.

## Key staff surfaces

| Area | Template | Notes |
|------|----------|-------|
| Bookings list | `staff_bookings.html` | Filters, manual booking dialog, HTMX search |
| Support | `staff/support.html` | Table + reply; not student chat layout |
| Reports | `staff/reports.html` | Form + Excel download |
| CRUD | `staff/disciplines.html`, `lab_works`, `rooms`, `stands`, `schedule`, `people` | Classic POST forms |
| Lab head | `lab_head/*` | Bindings, people, schedule — complete stubs, scoped forms |

## Manual booking checklist

- Student search: `hx-get` with `delay:300ms` → `staff_manual_student_results.html`
- Calendar chain: `#manual-filter-chain`, `#manual-session-slot` (mirror student ids)
- `htmx.ajax` when lab work id known dynamically
- POST `staff-booking-manual` with `student_id`, `session_id`, CSRF
- Manual path uses `BookingService` with `manual=True`, `skip_student_rules=True`

## Checklist

- Include CSRF protection on POST forms.
- Preserve message feedback for success and failure paths.
- Direct access to foreign objects should return 403/404 or redirect without mutation.
- Empty states should be clear for staff without data or without a lab binding.
- Student and staff calendar flows may share service helpers and filter partials but must keep manual booking mode explicit via `filter_route` context.

## Commands

```bash
cd backend
pytest apps/bookings/tests/test_manual_booking.py -v
pytest apps/bookings/tests/test_lab_head_ui.py -v
pytest apps/bookings/tests/test_staff_scope.py -v
```

## Manual scenarios

- Staff searches a student by full name, email, and group.
- Staff chooses lab work, date, pair, room and creates a manual booking.
- Staff changes booking status and replies to support.
- Lab head creates a person, assigns disciplines, creates lab work, stand, and schedule entry.

## Agent prompt template

```text
/labbooking-htmx-staff-ui
/labbooking-htmx-patterns
/labbooking-access-scope

Staff page: <name>. Tables and forms, HTMX only where needed.
Files: @staff/ @staff_bookings.html
```
