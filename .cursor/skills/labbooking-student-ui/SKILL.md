---
name: labbooking-student-ui
description: Student-facing web UI in labbooking — booking wizard, disciplines catalog, my bookings, support tickets, login. Mobile-first polish and brand image. Use when changing student templates, student CSS, student navigation, or student HTMX flows. Not for staff/lab-head admin tables.
---

# labbooking-student-ui

Use for student-facing pages: home (student branch), login, disciplines, lab works, book wizard, my bookings, booking detail, support list/detail, patch notes.

Pair with `labbooking-htmx-patterns` for HTMX partials and `ui-ux-pro-max` for UX quality. Pair with `labbooking-access-scope` when templates show scoped data.

## Zones

| Student (this skill) | Staff (use `labbooking-htmx-staff-ui`) |
|----------------------|----------------------------------------|
| Cards, wizard, bottom nav | Tables, dialogs, row-actions |
| Mobile-first | Dense data, minimal animation |
| Brand / perceived quality | Speed and clarity for operators |

## Layout

- Prefer `{% extends "base_student.html" %}` for student pages; `base_staff.html` for staff/lab-head.
- Student nav: Disciplines · My bookings · Support (≤5 items; bottom nav on mobile when `base_student` exists).
- Staff/lab-head nav must not leak into student-only templates.

## Pages and patterns

| Template | Pattern |
|----------|---------|
| `bookings/home.html` (student) | Hero + quick-action cards; no emoji icons — use SVG, numbered badges, or `action-card__icon` text |
| `bookings/disciplines.html` | Flat catalog with search; avoid deep nested `<details>` (cafedra → discipline → LR) on mobile |
| `bookings/lab_works.html` | `lab-grid` + `lab-card`; primary CTA «Записаться» |
| `bookings/book.html` | `booking-layout`, stepper, `#filter-chain` + `#session-slot`; delegate calendar to shared partials |
| `bookings/my_bookings.html` | `booking-cards` on mobile; table optional on desktop; `hx-confirm` on cancel when added |
| `bookings/support.html` | Form + ticket list; chat-like cards, not staff tables |
| `bookings/support_detail.html` | `thread` messages; reply form below thread |
| `registration/login.html` | Branded narrow card; match university identity |

## UX checklist (student)

- Touch targets ≥44px; calendar day buttons large on mobile.
- Loading: `hx-indicator` or skeleton on `#filter-chain` / `#session-slot` during HTMX swaps.
- Empty states with a clear next action (link to disciplines or support).
- Destructive actions (cancel booking): confirm before POST.
- Visible labels on forms; errors near fields.
- No horizontal scroll on 375px viewport.
- Respect `prefers-reduced-motion` for animations.
- Focus management after HTMX swap when focus would be lost.

## HTMX (student)

- Cascade booking filters: shared partials under `bookings/partials/` with `filter_route` / `filter_chain_selector` context.
- Search disciplines: `hx-trigger="input changed delay:300ms"` → small partial (not full page).
- Optional: `hx-boost="true"` on student nav links for faster transitions.
- Do not use staff-only patterns: `row-actions`, manual booking dialog, dense `responsive-table` as primary layout.

## Business logic boundaries

- Booking rules: `BookingService` (`labbooking-booking-service` skill) — not in templates.
- Visibility: student querysets (`labbooking-access-scope`) — views must scope before render.
- Manual booking (`manual=True`, `skip_student_rules=True`) is staff-only.

## CSS

- Use design tokens from `main.css` (`labbooking-design-system` skill).
- Student overrides go in `static/css/student.css` when split; do not fork token definitions.
- Reuse: `.card`, `.button`, `.status-badge--*`, `.booking-step`, `.empty-state`, `.thread`.

## API-first (future mobile app)

New student features: service → `/api/v1/` endpoint → web view. Do not add student-only business rules only in templates.

## Commands

```bash
cd backend
pytest apps/bookings/tests/test_student_scope.py -v
pytest apps/bookings/tests/test_booking.py -v
```

## Manual scenarios

- Student opens disciplines → lab work → calendar → pair → confirms → «Записаться» enabled.
- Student sees only group-scoped disciplines and lab works.
- Student cancels booking within deadline; blocked after 24h rule.
- Student creates support ticket and adds a follow-up message.
- My bookings readable on phone without horizontal scroll.

## Agent prompt template

```text
/labbooking-student-ui
/ui-ux-pro-max

Page: <name>. Mobile-first, no React. Match existing tokens in main.css.
Files: @bookings/<template>.html @static/css/main.css
```
