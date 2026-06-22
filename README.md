# Lab Booking — система записи на лабораторные работы

MVP системы электронной записи студентов на лабораторные работы (аналог [lr.spmi.ru](https://lr.spmi.ru/)).

**Стек:** Django 5 + DRF + PostgreSQL + Redis + Docker + HTMX

## API

- Swagger UI: http://localhost:8000/api/docs/
- OpenAPI schema: http://localhost:8000/api/schema/
- Health: http://localhost:8000/api/health/

> Поле логина в JWT — `email` (не `username`).

### Основные эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/v1/disciplines/` | Список дисциплин |
| GET | `/api/v1/sessions/?lab_work=1` | Доступные слоты |
| POST | `/api/v1/bookings/` | Записаться |
| GET | `/api/v1/me/bookings/` | Мои записи |
| POST | `/api/v1/bookings/{id}/cancel/` | Отменить запись |
| GET | `/api/v1/sessions/filters/?lab_work=1` | Каскадные фильтры слотов |
| POST | `/api/v1/waitlist/` | Встать в очередь |
| POST | `/api/v1/support/tickets/{id}/messages/` | Сообщение в тикете |
| GET | `/api/v1/admin/reports/{type}/` | Excel-отчёт (staff) |

## Бизнес-правила

- Запись на **14 дней** вперёд
- Отмена студентом **за 24 часа** до начала
- **1 активная запись** на дисциплину
- Статусы: Записан, Неявка, Отменил запись, Повторный доступ, Посетил

## Production / VM (Yandex Cloud)

```bash
cp .env.vm.example .env
# отредактируйте ALLOWED_HOSTS, SECRET_KEY, пароли
bash scripts/deploy-vm.sh
```

Подробно: [docs/DEPLOY_YANDEX_VM.md](docs/DEPLOY_YANDEX_VM.md)  
Дорожная карта: [docs/ROADMAP.md](docs/ROADMAP.md)  
План пилота: [docs/PILOT_PLAN.md](docs/PILOT_PLAN.md)

```bash
# или вручную:
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d --build
```

Установите в `.env`: `DEBUG=0`, `DJANGO_SETTINGS_MODULE=config.settings.prod`, `SECURE_SSL_REDIRECT=0` (до настройки HTTPS).

## Структура

```
backend/
  apps/users/       — User, Profile, SSO adapter
  apps/academics/   — Semester, Discipline, LabWork
  apps/scheduling/  — Room, LabSession, Holiday
  apps/bookings/    — Booking, services, API, web UI
```

## Тесты

```bash
cd backend && pytest
```

## Cursor Agent Skills

Skills лежат в `.cursor/skills/` и синхронизируются через git.

```bash
git pull
git submodule update --init --recursive
```

Подробно: [docs/CURSOR_SKILLS.md](docs/CURSOR_SKILLS.md)

Примеры вызова в Agent chat: `/labbooking-vm-deploy`, `/labbooking-prod-security`, `/ui-ux-pro-max`, `/anthropic-cybersecurity`.

## Cybersecurity

Проектный чеклист: `.cursor/rules/security.md` и skill `/labbooking-prod-security`.

Библиотека Anthropic Cybersecurity Skills подключена как git submodule:

`.cursor/skills/vendor/Anthropic-Cybersecurity-Skills/`

Wrapper-skill: `/anthropic-cybersecurity`
