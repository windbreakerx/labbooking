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
/labbooking-vm-deploy
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
| `labbooking-htmx-staff-ui` | HTMX templates, staff/lab-head UI |
| `labbooking-pytest-pilot` | pytest gate перед merge/deploy |
| `labbooking-vm-deploy` | Docker, VM, `.env`, HTTPS, backup |
| `labbooking-dekanat-csv` | CSV import, pilot data templates |
| `labbooking-prod-security` | Security gate проекта перед prod |
| `labbooking-pilot-data-setup` | `seed_demo`, CSV, acceptance data |

## Внешние skills в репозитории

| Skill | Путь | Примечание |
|-------|------|------------|
| `anthropic-cybersecurity` | `.cursor/skills/anthropic-cybersecurity/` | Wrapper над submodule |
| Anthropic library | `.cursor/skills/vendor/Anthropic-Cybersecurity-Skills/` | Git submodule, ~754 skills |
| `ui-ux-pro-max` | `.cursor/skills/ui-ux-pro-max/` | UI/UX для HTMX templates |

## Примеры промптов

```text
/labbooking-access-scope

Закрой scoping в staff API для SupportTicket. Один чат = одна фича.
```

```text
/labbooking-prod-security @.cursor/rules/security.md

Security review перед деплоем на VM.
```

```text
/ui-ux-pro-max

Улучши staff bookings page: фильтры, пустые состояния, accessibility. Без React.
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

Один чат = одна фича. В начале чата указывайте один skill и нужные файлы/docs.
