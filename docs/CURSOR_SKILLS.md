# Cursor Agent Skills для labbooking

Skills хранятся в репозитории, чтобы одинаково работать с разных компьютеров после `git pull`.

## Первый запуск на новом компьютере

```bash
git pull
git submodule update --init --recursive
```

Перезапустите Cursor после первого pull, если skills не видны в **Settings → Rules → Agent Skills**.

## Как вызывать

### Автоматически

В **Agent mode** Cursor подбирает skill по `description` в frontmatter и контексту задачи.

### Вручную (надёжнее)

В Agent chat:

```text
/labbooking-student-ui
```

или

```text
/ui-ux-pro-max
```

## Project skills labbooking

| Skill | Когда использовать |
|-------|-------------------|
| `labbooking-booking-service` | Запись, отмена, статусы, `BookingService` |
| `labbooking-access-scope` | Scoping student/staff/lab-head, querysets, API |
| `labbooking-student-ui` | Студент: дисциплины, wizard записи, мои записи, support, login |
| `labbooking-htmx-patterns` | HTMX partials, `hx-*`, cascade filters, `afterSwap`, dialogs |
| `labbooking-htmx-staff-ui` | Staff/lab-head: таблицы, ручная запись, CRUD |
| `labbooking-design-system` | `main.css` tokens, BEM, student vs staff CSS |
| `labbooking-pytest-pilot` | pytest gate перед merge/deploy |
| `labbooking-vm-deploy` | Docker, VM, `.env`, HTTPS, backup |
| `labbooking-dekanat-csv` | CSV import, pilot data templates |
| `labbooking-prod-security` | Security gate проекта перед prod |
| `labbooking-pilot-data-setup` | `seed_demo`, CSV, acceptance data |

## Cursor rules (frontend)

| Rule | Globs | Когда |
|------|-------|-------|
| `.cursor/rules/frontend.mdc` | `backend/templates/**`, `backend/static/**` | Любая правка шаблонов/CSS |
| `.cursor/rules/security.md` | — | Security review (вручную в промпте) |

## Внешние skills в репозитории

| Skill | Путь | Примечание |
|-------|------|------------|
| `anthropic-cybersecurity` | `.cursor/skills/anthropic-cybersecurity/` | Wrapper над submodule |
| Anthropic library | `.cursor/skills/vendor/Anthropic-Cybersecurity-Skills/` | Git submodule, ~754 skills |
| `ui-ux-pro-max` | `.cursor/skills/ui-ux-pro-max/` | UI/UX для web/mobile; парный skill для student UI |

## Комбо-промпты (frontend)

### Студент — новая страница или полировка

```text
/ui-ux-pro-max
/labbooking-student-ui
/labbooking-design-system

Страница: disciplines — плоский каталог, mobile-first.
Файлы: @bookings/disciplines.html @static/css/main.css
```

Перед дизайном (опционально, из корня skill):

```bash
python .cursor/skills/ui-ux-pro-max/scripts/search.py "university student portal booking mobile" --design-system -p "labbooking-student"
```

### Wizard записи (HTMX + сервис)

```text
/labbooking-student-ui
/labbooking-htmx-patterns
/labbooking-booking-service

book.html: loading states, skeleton, stepper. Не менять BookingService.
```

### Staff — таблица / ручная запись

```text
/labbooking-htmx-staff-ui
/labbooking-htmx-patterns
/labbooking-access-scope

staff_bookings: HTMX фильтр. Таблица, без student cards.
pytest apps/bookings/tests/test_manual_booking.py -v
```

### HTMX partial (общий)

```text
/labbooking-htmx-patterns

Новый partial для каскадного фильтра. CSRF, filter_route context.
```

### ui-ux-pro-max + Laravel stack как аналог HTMX

```bash
python .cursor/skills/ui-ux-pro-max/scripts/search.py "loading server form" --stack laravel
```

Livewire/Alpine guidelines в skill map к HTMX/Alpine в labbooking.

## Примеры промптов (backend)

```text
/labbooking-access-scope

Закрой scoping в staff API для SupportTicket. Один чат = одна фича.
```

```text
/labbooking-prod-security @.cursor/rules/security.md

Security review перед деплоем на VM.
```

## Обновление внешних skills

Anthropic submodule:

```bash
git submodule update --remote .cursor/skills/vendor/Anthropic-Cybersecurity-Skills
git add .cursor/skills/vendor/Anthropic-Cybersecurity-Skills .gitmodules
git commit -m "Update Anthropic Cybersecurity Skills submodule."
```

ui-ux-pro-max vendored in repo — обновляйте вручную из upstream при необходимости.

## Правило проекта

Один чат = одна фича. В начале чата указывайте skill(и) и нужные файлы/docs.

**Student vs staff:** student = имидж + mobile (`labbooking-student-ui`); staff = простые таблицы (`labbooking-htmx-staff-ui`).
