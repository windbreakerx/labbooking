---
name: labbooking-htmx-patterns
description: HTMX and vanilla JS patterns for labbooking Django templates — partials, cascade filters, calendar, dialogs, loading states, afterSwap handlers. Use when adding or changing hx-* attributes, partial templates, or small JS hooks for server-driven UI.
---

# labbooking-htmx-patterns

Use when adding `hx-*` attributes, partial templates, `htmx:afterSwap` handlers, or `<dialog>` + HTMX combinations.

Staff-specific page rules: `labbooking-htmx-staff-ui`. Student polish: `labbooking-student-ui`.

## Principles

- Server renders HTML fragments; business logic stays in views/services/querysets.
- Partials are small and replaceable (`innerHTML` swap on a stable container id).
- Every POST form includes `{% csrf_token %}`.
- Prefer declarative `hx-*` over `htmx.ajax()` unless dynamic URL (e.g. manual booking lab work id).

## Shared partial conventions

Cascade filter partials accept optional context:

| Variable | Default | Purpose |
|----------|---------|---------|
| `filter_route` | `'book-filter'` | URL name for `{% url filter_route lab_work_id %}` |
| `filter_chain_selector` | `'#filter-chain'` | `hx-target` for chain replacements |
| `lab_work_id` | required | Lab work pk in filter URLs |

Key partials:

- `bookings/partials/filter_date_calendar.html` — heat-map calendar; date pick replaces `#filter-chain`
- `bookings/partials/filter_pair.html`, `filter_room.html`, `filter_tc.html`, `filter_time.html`, `filter_date.html` — cascade steps
- `bookings/partials/session_select.html`, `session_confirm.html` — slot into `#session-slot`
- `bookings/partials/staff_manual_student_results.html` — staff search results
- `bookings/partials/staff_status_form.html` — staff status inline form

## Student booking wizard (`book.html`)

Containers:

- `#filter-chain` — cascade partials; clearing `#session-slot` on chain reset
- `#session-slot` — session select or confirm summary
- `#book-btn` — disabled until valid `session_id`

JS pattern (keep in template or small inline block):

```javascript
document.body.addEventListener('htmx:afterSwap', function (evt) {
  // filter-chain swap → clear session-slot, disable book-btn
  // session-slot swap → enable book-btn when session_id present
  // updateBookingStepper() for .booking-step--active / --done
});
```

Stepper: `.booking-stepper [data-step]` — update from DOM state, not separate API.

## Staff manual booking (`staff_bookings.html`)

- `<dialog id="manual-booking-dialog">` opened via vanilla JS.
- `#manual-filter-chain`, `#manual-session-slot` mirror student chain ids.
- Dynamic load when lab work selected:

```javascript
htmx.ajax('GET', '/staff/bookings/manual/filter/' + labWorkId + '/', {
  target: '#manual-filter-chain',
  swap: 'innerHTML'
});
```

Pass `filter_route` and `filter_chain_selector` from view context for manual filter partials.

## HTMX attribute patterns

| Need | Pattern |
|------|---------|
| Debounced search | `hx-trigger="input changed delay:300ms, search"` |
| Cascade filter | `hx-get` + `hx-include="{{ filter_chain_selector }}"` |
| Replace chain | `hx-target="#filter-chain"` `hx-swap="innerHTML"` |
| Loading | `hx-indicator="#id"` + CSS `.htmx-request` on indicator |
| Confirm destroy | `hx-confirm="…"` on cancel/delete |
| Toast (optional) | Response with `hx-swap-oob="true"` fragment |

Load HTMX from static in production (`{% static 'js/htmx.min.js' %}`), not CDN.

## Loading and feedback

- Add `hx-disabled-elt="this"` or disable submit during request.
- Show spinner/skeleton on target container while `htmx-request` class is active.
- Preserve Django `messages` on full-page fallback; for partial POST return message fragment or redirect.

## Vanilla JS (allowed scope)

- `details.row-actions` — close other menus, flip menu if near viewport edge (`base.html`).
- Dialog open/close via `data-dialog-close` and `<dialog>`.
- `htmx:afterSwap` for book-btn, stepper, manual booking enable state.
- Do not move booking rules or validation into JS.

## Alpine.js (student only, optional)

- Local UI: mobile drawer, tabs, client-side discipline filter without round-trip.
- Do not use Alpine for booking mutations or scope checks.

## View responsibilities

HTMX filter views return partial templates only (no full `base.html` extend).

- Student: `BookFilterWebView` / book-filter route in `views/web.py`
- Staff manual: manual filter route in staff views
- Set `filter_route`, `filter_chain_selector`, `calendar_months`, `filter_options` in context

## Commands

```bash
cd backend
pytest apps/bookings/tests/test_manual_booking.py -v
pytest apps/bookings/tests/test_booking.py -v
```

## ui-ux-pro-max analog

Livewire rules in `ui-ux-pro-max` (`--stack laravel`) map to HTMX: `wire:loading` → `hx-indicator`; `wire:model.live` → `hx-trigger` with delay; Alpine → local student UI only.

## Agent prompt template

```text
/labbooking-htmx-patterns
/labbooking-booking-service

Add HTMX partial for <feature>. CSRF on POST. No business logic in template.
Files: @partials/ @views/web.py
```
