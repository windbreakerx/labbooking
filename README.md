# Lab Booking — система записи на лабораторные работы

MVP системы электронной записи студентов на лабораторные работы (аналог [lr.spmi.ru](https://lr.spmi.ru/)).

**Стек:** Django 5 + DRF + PostgreSQL + Redis + Docker + HTMX


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

## Cybersecurity

```bash
npx skills add mukul975/Anthropic-Cybersecurity-Skills
```

См. `.cursor/rules/security.md` для чеклиста безопасности проекта.
