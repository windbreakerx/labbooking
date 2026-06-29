---
name: labbooking-design-system
description: CSS design tokens and component classes for labbooking — main.css variables, BEM components, student vs staff styling. Use when adding or changing styles, new UI components, layout, or responsive behavior in static/css or template class names.
---

# labbooking-design-system

Use when editing `backend/static/css/main.css`, `student.css`, or choosing class names in templates.

Pair with `labbooking-student-ui` for student-specific layout; staff pages reuse `main.css` components with minimal overrides.

## Token source

All custom CSS reads from `:root` in `backend/static/css/main.css`:

| Category | Examples |
|----------|----------|
| Colors | `--color-primary`, `--color-bg`, `--color-danger`, `--color-success-soft` |
| Legacy aliases | `--bg`, `--card`, `--accent`, `--border` (for older templates) |
| Typography | `--font-sans`, `--text-sm` … `--text-2xl`, `--font-weight-heading` |
| Spacing | `--space-1` … `--space-12` |
| Radii | `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-pill` |
| Shadows | `--shadow-sm`, `--shadow-md`, `--shadow-focus` |
| Layout | `--container-max`, `--header-height`, `--content-max-width` |
| Breakpoints | `--bp-sm` 480, `--bp-md` 768, `--bp-lg` 1024, `--bp-xl` 1280 |
| Motion | `--transition-fast`, `--transition-base`, `--prefers-reduced-motion` |

**Do:** `color: var(--color-primary);` `padding: var(--space-4);`

**Don't:** new random hex in templates or component rules; duplicate token blocks in `student.css`.

## Component classes (reuse before inventing)

| Component | Classes |
|-----------|---------|
| Layout | `.container`, `.page-shell`, `.page-header`, `.breadcrumbs` |
| Cards | `.card`, `.card--narrow`, `.card--interactive`, `.card--form`, `.card__header`, `.card__title` |
| Buttons | `.button`, `.button--secondary`, `.button--ghost`, `.button--sm` |
| Badges | `.badge`, `.badge--muted`, `.badge--warning` |
| Status | `.status-badge`, `.status-badge--booked`, `--cancelled`, `--open`, … |
| Forms | `.form-grid`, `.form-actions`, `.muted` |
| Empty | `.empty-state`, `.empty-state--icon` |
| Tables (staff) | `.table`, `.responsive-table`, `.table-wrap`, `data-label` on cells |
| Booking | `.booking-layout`, `.booking-wizard`, `.booking-stepper`, `.booking-step--active` |
| Calendar | `.calendar-card`, `.calendar-day--available`, `--heat` CSS variable |
| Support | `.thread`, `.thread__message--own`, `.ticket-card` |
| Dialog | `.app-dialog`, `.app-dialog__actions` |
| Staff actions | `details.row-actions`, `.row-actions__menu` |
| Nav | `.header`, `.nav`, `.nav__section`, `.nav__link--current` |

## BEM naming

- Block: `.booking-card`, Element: `.booking-card__header`, Modifier: `.booking-step--done`
- Match existing double-dash modifiers in the file before introducing new naming schemes.

## Student vs staff CSS split

| File | Audience |
|------|----------|
| `main.css` | Shared tokens + staff-default components |
| `student.css` (when added) | Student layout, bottom nav, hero, card-first my-bookings |

Link in base templates:

```html
<link rel="stylesheet" href="{% static 'css/main.css' %}?v=…">
<!-- base_student only -->
<link rel="stylesheet" href="{% static 'css/student.css' %}?v=…">
```

Cache-bust with `?v=` date stamp when changing CSS.

## Responsive rules

- Mobile-first: default styles for narrow; `@media (min-width: …)` using `--bp-md` / `--bp-lg`.
- Student: prefer `.booking-cards--mobile` visible, hide dense tables on small screens.
- Staff: `.responsive-table` with `data-label` for stacked cells.
- Use `min-h-dvh` over `100vh` for full-height student shells when needed.

## Accessibility in CSS

- `:focus-visible` with `var(--shadow-focus)` — do not remove focus rings.
- `.skip-link` pattern available for keyboard users.
- Sufficient contrast on `.muted` text against surfaces.
- `@media (prefers-reduced-motion: reduce)` for non-essential animations.

## Icons

- SVG or CSS badges — not emoji as UI icons (especially student home/actions).
- Logo: `static/img/spmi-logo.png` / `.svg`.

## Adding a new component

1. Check if `.card` + modifiers already fit.
2. Add tokens only if truly new semantic color/spacing needed.
3. Place rules in logical section of `main.css` (or `student.css` if student-only).
4. Use existing spacing scale — no `padding: 13px`.

## Agent prompt template

```text
/labbooking-design-system
/labbooking-student-ui

Add styles for <component>. Reuse tokens and existing BEM blocks.
Files: @static/css/main.css @templates/...
```
