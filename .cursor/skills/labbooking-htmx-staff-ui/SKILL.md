---
name: labbooking-htmx-staff-ui
description: Guides HTMX staff and lab-head UI changes in labbooking without moving business logic into templates. Use when changing Django templates, HTMX partials, staff booking pages, manual booking, support replies, filters, or calendar UI.
---

# labbooking-htmx-staff-ui

Use this skill when changing Django templates, HTMX partials, staff booking pages, manual booking, support replies, lab-head pages, filters, or calendar selection UI.

## UI Boundaries

- Keep business decisions in services/querysets, not templates.
- HTMX partials should render small, replaceable fragments from server-side state.
- Staff and lab-head pages must use scoped querysets before rendering data.

## Checklist

- Include CSRF protection on POST forms.
- Preserve message feedback for success and failure paths.
- Direct access to foreign objects should return 403/404 or redirect without mutation.
- Empty states should be clear for staff without data or without a lab binding.
- Student and staff calendar flows may share service helpers but must keep manual booking mode explicit.

## Commands

```bash
cd backend
pytest apps/bookings/tests/test_manual_booking.py -v
pytest apps/bookings/tests/test_lab_head_ui.py -v
pytest apps/bookings/tests/test_staff_scope.py -v
```

## Manual Scenarios

- Staff searches a student by full name, email, and group.
- Staff chooses lab work, date, pair, room and creates a manual booking.
- Staff changes booking status and replies to support.
- Lab head creates a person, assigns disciplines, creates lab work, stand, and schedule entry.
