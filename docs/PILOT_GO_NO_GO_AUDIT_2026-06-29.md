# Продуктово-технический аудит labbooking перед пилотом

**Дата:** 29.06.2026  
**Сайт:** https://spmi-lab.ru  
**Стек:** Django 5, DRF, HTMX, PostgreSQL, Redis  
**Роли:** STUDENT, LAB_ADMIN, LAB_HEAD, SYS_ADMIN  

**Модель аудита:** продукт + UX + готовность к пилоту (без построчного security review).

---

## Источники

| Источник | Статус |
|----------|--------|
| `README.md` | ✅ в репо |
| `docs/PILOT_PLAN.md` | ✅ в репо |
| `docs/PILOT_ACCEPTANCE_CHECKLIST.md` | ✅ в репо |
| `docs/ROADMAP.md` | ✅ в репо |
| `docs/api.md` | ✅ в репо |
| `docs/students_tz.txt` | ❌ **отсутствует в репо** |
| `docs/zavlab_tz.txt` | ❌ **отсутствует в репо** |
| PDF ТЗ студентов / завлабов (Desktop) | ✅ использованы как эталон |
| Живой сайт spmi-lab.ru | ✅ проверен (public + student + lab_head) |
| Логин LAB_ADMIN | ❌ не предоставлен — staff только по коду/шаблонам |

**Рекомендация:** добавить `docs/students_tz.txt` и `docs/zavlab_tz.txt` в репозиторий или явно сослаться на PDF в `PILOT_PLAN.md`.

---

## Executive summary

1. **Student booking flow на проде** — зафиксирован сбой (форма логина внутри панели записи); без исправления пилот для студентов не открывать.
2. **Lab head: «Сотрудники» и «Расписание»** — на prod UI заглушка «На доработке» при живом backend; блокер сценария завлаба из ТЗ.
3. **Staff end-to-end** — код/шаблоны богаты, но без LAB_ADMIN аккаунта не подтверждён на spmi-lab.ru.
4. **Email** — шаблоны и `_send_email` есть; доставка пользователю на prod не подтверждена (`EMAIL_FAIL_SILENTLY` по умолчанию true).
5. **Данные семестра** — scoping по `StudentGroup` реализован; риск = качество CSV/seed, не только код.
6. **Отчёты Excel** — есть 3 типа, но состав слабее ТЗ (нет пола, должности, накопленной истории статусов и т.д.).
7. **SSO / API Деканата** — заглушки; для узкого пилота допустимо при явном scope.
8. **UX mobile** — login/post-login layout, перегруженная навигация staff/lab_head на узких экранах.
9. **Студентский flow записи в коде** — упрощён vs ТЗ: «дата → пара → подтверждение» (УЦ/аудитория подставляются автоматически); это осознанное упрощение MVP.
10. **Автотесты** — в сессии аудита локальный прогон pytest не подтверждён; перед go обязателен прогон по `PILOT_ACCEPTANCE_CHECKLIST`.

---

# Часть A. Go / No-Go перед стартом пилота

## Решение

| Вердикт | Условие |
|---------|---------|
| **NO-GO** | Любой пункт из таблицы P0 ниже = ❌ в день проверки |
| **GO (узкий пилот)** | Все P0 = ✅, P1 допустимы с письменным waver и датой закрытия |
| **GO (полная приёмка по ТЗ)** | P0 + P1 + расширенные отчёты + полный UI завлаба |

## P0 — обязательны в день запуска (зелёные = можно открывать)

Проверяющий: _______________  Дата: _______________  Среда: **prod** https://spmi-lab.ru

| # | Критерий | Как проверить | URL / команда | ✅/❌ | Комментарий |
|---|----------|---------------|---------------|-------|-------------|
| P0-1 | Student: вход | Логин тестового студента | `/login/` | | |
| P0-2 | Student: дисциплины только своей группы | Список без «чужих» кафедр/ЛР; прямой URL foreign id → 403/404 | `/disciplines/` | | |
| P0-3 | Student: запись end-to-end | Дата → пара → подтверждение → «Записаться» → success | `/lab-works/<id>/book/` | | **Блокер на момент аудита** |
| P0-4 | Student: «Мои записи» | Запись видна с УЦ, ауд., датой, статусом | `/my-bookings/` | | |
| P0-5 | Student: отмена за 24 ч | Отмена активной записи до дедлайна; после дедлайна — отказ | `/my-bookings/<id>/cancel/` | | |
| P0-6 | Student: обращение | Создать тикет в доступную лабораторию | `/support/` | | |
| P0-7 | Staff: записи своей лаборатории | LAB_ADMIN видит только свой УЦ/лабу | `/staff/bookings/` | | Нужен аккаунт |
| P0-8 | Staff: смена статуса | VISITED / NO_SHOW / REACCESS / CANCELLED | `/staff/bookings/` | | |
| P0-9 | Staff: ручная запись | Поиск студента → календарь → запись | `/staff/bookings/` (dialog) | | |
| P0-10 | Staff: ответ на обращение | Reply в scope лаборатории | `/staff/support/` | | |
| P0-11 | Lab head: привязки дисциплин/ЛР | Bind/unbind работает | `/lab-head/bindings/` | | |
| P0-12 | Lab head: ЛР и стенды | CRUD минимум для пилота | `/lab-head/lab-works/`, `/lab-head/stands/` | | |
| P0-13 | Lab head: люди ИЛИ waver | Раздел не заглушка **или** письменное исключение из scope | `/lab-head/people/` | | **Заглушка на prod** |
| P0-14 | Lab head: расписание ИЛИ waver | То же | `/lab-head/schedule/` | | **Заглушка на prod** |
| P0-15 | Email (минимум) | SMTP test + письмо на «запись» и «отмена» | `.env`, `manage.py shell` | | |
| P0-16 | Данные пилота | Группы, curriculum, ЛР, слоты ≥ 2 недель | CSV + `generate_sessions` | | |
| P0-17 | Backup БД | `backup_db.sh` перед go-live | `scripts/backup_db.sh` | | |
| P0-18 | Автотесты | Все suite из checklist | см. раздел «Automated checks» | | |
| P0-19 | Scoping smoke | Нет чужих записей/тикетов «на глаз» | student + staff URLs | | |
| P0-20 | Health / deploy | Smoke после деплоя | `scripts/smoke-test.sh` | | |

### P0 blockers (зафиксировано на 29.06.2026)

- [ ] **P0-3** — booking flow на prod (HTMX / сессия)
- [ ] **P0-13, P0-14** — UI заглушки lab_head people/schedule
- [ ] **P0-7–P0-10** — не пройдены без LAB_ADMIN логина
- [ ] **P0-15** — SMTP не подтверждён в аудите
- [ ] **P0-18** — pytest не прогнан в сессии аудита

## P1 — желательно до пилота (waver допустим)

| # | Критерий | Где |
|---|----------|-----|
| P1-1 | Mobile: login и post-login без «уехавшей» вёрстки | `login.html`, `main.css` |
| P1-2 | HTMX loading/error у шагов записи | `book.html`, partials |
| P1-3 | Честные empty states staff (нет данных / нет training_center) | `staff_bookings.html` |
| P1-4 | Отчёты: минимальный набор полей ТЗ | `reports.py` |
| P1-5 | Support: различать Answered vs Closed в UI | `staff/support.html` |
| P1-6 | Skip-link / focus для a11y | `base.html` (класс `.skip-link` в CSS есть, в base не подключён) |
| P1-7 | Инструкция 1 страница для студентов | контент, не код |

## Явно после пилота (не блокируют узкий GO)

- SSO / OIDC (`SSO_ENABLED`, `api/v1/auth/sso/`)
- API Деканата (real-time sync)
- Полное соответствие Excel ТЗ (расширенная история, пол, должность)
- SPA / React
- Интерактивная карта аудиторий
- Очередь ожидания как отдельный продуктовый сценарий

## Sign-off

| Роль | ФИО | Go / No-Go / Go с waver | Дата |
|------|-----|-------------------------|------|
| Продукт / завлаб | | | |
| ОУЛО / оператор | | | |
| Разработка | | | |

---

# Часть B. Соответствие ТЗ (продуктовый разрез)

## Студент (`students` PDF + PILOT_PLAN)

| Приоритет | Область | Статус | Где | Блокер? | Рекомендация |
|-----------|---------|--------|-----|---------|--------------|
| P0 | Вход (локальный email, не SSO) | ⚠️ | `/login/`, `WebLoginView` | Нет* | *ТЗ lr.spmi.ru — корп. почта; для пилота — waver |
| P0 | Меню: дисциплины, мои записи, обращения | ✅ | `base.html`, `home.html` | Нет | — |
| P0 | Дисциплины по учебному плану группы | ✅ | `querysets.py`, `/disciplines/` | Нет | E2E на prod |
| P0 | Запись: дата, время, УЦ, аудитория | ⚠️ | UI: дата→пара→auto slot; ТЗ: 4 dropdown | Частично | Показать УЦ/ауд. в confirm (`session_confirm.html`) |
| P0 | Email после записи/отмены/статусов | ⚠️ | `booking.py` | Да без SMTP | Настроить SMTP |
| P0 | Мои записи + ⋮ просмотр/отмена | ✅ | `my_bookings.html` | Нет | Прогнать отмену |
| P0 | Статусы (5 шт.) | ✅ | `BookingStatus`, badges в UI | Нет | — |
| P0 | Обращения в лабораторию | ✅ | `/support/` | Нет | E2E с staff reply |
| P1 | Методички PDF у ЛР | ❓ | staff upload; student UI не проверен | Нет | Проверить доступ студенту |

## Staff / завлаб (`zavlab` PDF)

| Приоритет | Область | Статус | Где | Блокер? | Рекомендация |
|-----------|---------|--------|-----|---------|--------------|
| P0 | Записавшиеся + фильтры | ⚠️ | `/staff/bookings/` | Нет* | *Нужен live LAB_ADMIN |
| P0 | Смена статусов | ✅ | `StaffStatusUpdateWebView`, partial | Нет* | |
| P0 | Ручная запись | ✅ | dialog в `staff_bookings.html` | Нет* | |
| P0 | Support staff | ✅ | `/staff/support/` | Нет* | |
| P0 | Excel отчёты | ⚠️ | `/staff/reports/`, `reports.py` | Нет узкий / Да полный ТЗ | Расширить поля |
| P0 | Завлаб: люди | ❌ UI | views в `lab_head.py`, template stub | **Да** | Включить template или waver |
| P0 | Завлаб: расписание | ❌ UI | `LabHeadScheduleView` vs stub template | **Да** | То же |
| P0 | Завлаб: дисциплины/ЛР/стенды | ✅ | `/lab-head/bindings/`, lab-works, stands | Нет | |
| P1 | Сортировка по колонкам везде | ⚠️ | частично `sortable_th` | Нет | — |
| P1 | Деканат auto-import | ❌ заглушка | `integrations/dekanat.py` | Нет | CSV для пилота |
| P1 | Расписание «неделя 1/2», дежурства | ⚠️ | `ScheduleEntry`, упрощённая форма | После | — |

## Бизнес-правила

| Правило | Реализация | Статус |
|---------|------------|--------|
| 14 дней вперёд | `BOOKING_HORIZON_DAYS=14`, `booking_date_window()` | ✅ |
| Открытие дня 22:00, закрытие 15:00 | `BOOKING_DAY_OPENS_AT`, `BOOKING_DAY_CLOSES_AT` | ✅ |
| Отмена за 24 ч (студент) | `BOOKING_CANCEL_HOURS=24`, staff может иначе | ✅ |
| 1 активная запись на дисциплину | `_check_discipline_limit()` | ✅ |
| Праздники | `Holiday` model | ✅ |
| Статусы + история | `BookingStatusHistory` | ✅ |
| REACCESS при отмене слота | `cancel_session_with_reaccess()` | ✅ |
| Email тексты | `_send_email()` templates | ✅ код / ⚠️ доставка |
| SSO | `SSO_ENABLED=False`, stub API | ⚠️ после пилота |
| Деканат API | `DekanatClient` → CSV commands | ⚠️ после пилота |

---

# Часть C. Живая проверка spmi-lab.ru

## Public

| Ожидание | Факт |
|----------|------|
| Главная или логин | `/` → redirect `/login/` |
| Бренд SPMI, форма email+пароль | ✅ |
| Mobile layout | ⚠️ карточка/login прижаты, много пустоты |
| Утечка данных без логина | Не обнаружена |

## Student (`s210052@stud.spmi.ru`)

| Шаг | Ожидание ТЗ | Факт на экране |
|-----|-------------|----------------|
| Вход | OK | ✅ Набока Н.А. |
| Дисциплины | Только своя группа | ✅ 1 кафедра, 2 дисциплины, ЛР |
| Запись | Дата → … → Записаться | ❌ после выбора даты — форма логина в панели, кнопка disabled |
| Мои записи | Список / empty state | ✅ empty state |
| Отмена | После записи | ⏭ не проверено (нет записи) |
| Обращение | Форма + тикеты | ⏭ не проверено полностью |

**UX на prod:** длинные названия ЛР обрезаются; nested `<details>` — контент в a11y tree до раскрытия; клик по карточке ЛР иногда не ведёт на book (href работает).

## Lab head (`zavlab.pilot@spmi.ru`)

| Шаг | Ожидание | Факт |
|-----|----------|------|
| Кабинет | Dashboard | ✅ |
| Дисциплины / привязки | Bind, search | ✅ |
| Лаб. работы | Список, добавить | ✅ большой список |
| Стенды | Таблица | ✅ |
| Сотрудники | CRUD людей | ❌ «На доработке» |
| Расписание | Настройка слотов | ❌ «На dоработке» |
| Staff menu | Записавшиеся, support | ✅ (завлаб видит staff-разделы) |

**Примечание:** в одной сессии браузерного аудита после сбоя student flow наблюдалось смешение навигации student/lab_head — **требует контрольной перепроверки с явным logout между ролями** (P0-19).

## Staff (LAB_ADMIN)

Не проверено на prod — только код:

- `/staff/bookings/` — фильтры, таблица, manual dialog, status forms
- `/staff/support/`, `/staff/reports/`
- `/staff/disciplines/`, `/staff/lab-works/`, `/staff/stands/`, `/staff/schedule/` (read-only), `/staff/people/`

---

# Часть D. UX и дизайн

## Сильные стороны

- Единая дизайн-система в `backend/static/css/main.css` (токены SPMI-синий + золотой акцент)
- Роль-ориентированная навигация в `base.html`
- Student: card/table dual layout «Мои записи»
- Staff: manual booking dialog с HTMX search + calendar
- Lab head: dialogs для ЛР/стендов/аудиторий

## High-impact правки (HTMX, без React)

| # | Правка | Файлы / URL |
|---|--------|-------------|
| 1 | Починить prod booking HTMX chain | `book.html`, `partials/filter_*.html`, `BookFilterPartialView` |
| 2 | Stepper: 3 шага = 3 labels (убрать «Шаг 4») | `book.html`, `session_confirm.html`, `main.css` |
| 3 | `hx-indicator` + inline error на partial failures | partials + `main.css` |
| 4 | Mobile nav: collapse staff/lab_head blocks | `base.html`, `@media max-width 768px` |
| 5 | `body` → class `site` или убрать `body.site` из CSS | `base.html`, `main.css` |
| 6 | Emoji → SVG/номера в student home | `home.html` |
| 7 | `.catalog-lab-work__title` — wrap, не clip | `main.css`, `disciplines.html` |
| 8 | Support status labels | `staff/support.html`, student `support.html` |
| 9 | Lab head stubs → реальные templates или banner «не в пилоте» | `lab_head/people.html`, `lab_head/schedule.html` |
| 10 | Skip link в `base.html` | уже стилизован в CSS |

## Accessibility (кратко)

- Focus rings: ✅ в CSS
- Skip link: стили есть, **не в разметке**
- Контраст primary: в целом OK
- Touch targets calendar-day: ~2.5rem — на грани для mobile
- Screen reader: скрытый контент в `<details>` до expand — улучшить aria

---

# Часть E. Feature backlog

| Фича | Боль | Ценность | S/M/L | Когда | Зависимости |
|------|------|----------|-------|-------|-------------|
| Прогресс по дисциплине (N/M ЛР) | Непонятно что осталось | Меньше обращений | M | После | Booking history |
| Bulk status change staff | Рутина в конце дня | Время staff | M | После | BookingService |
| «Ближайший слот» CTA | Много кликов | Быстрая запись | S | **До** | session_availability |
| Audit trail в UI | «Кто отменил» | Доверие | M | До/После | AuditLog |
| Отчёты по ТЗ v2 | Отчётность кафедры | Compliance | L | После | reports.py |
| SLA dashboard support | Просроченные тикеты | Качество поддержки | S | **До** | `is_response_overdue` |
| CSV import preview | Битые группы | Старт семестра | M | **До** | import_dekanat_csv |
| Email reminder T-24h | Неявки | Снижение no-show | M | После | SMTP, cron |
| Мастер расписания 1/2 неделя | Сложная настройка | Онбординг лаб | M | После | ScheduleEntry |
| Help «Как записаться» | FAQ поток | Нагрузка на staff | S | **До** | static page |

---

# Часть F. Матрица готовности

| Контур | ~% | Главный риск | Проверить на spmi-lab.ru |
|--------|-----|--------------|--------------------------|
| Студент | 70% | Broken booking flow | P0-1…P0-6 |
| Staff | 75%* | Нет live аккаунта | P0-7…P0-10 |
| Lab head | 65% | People/schedule stubs | P0-11…P0-14 |
| Email/ops | 60% | SMTP silent fail | P0-15, P0-17 |
| Данные/scoping | 75%* | CSV quality | P0-2, P0-16, P0-19 |

\* по коду; prod частично не подтверждено

---

# Часть G. План 1–2 недели

## Неделя 1 (P0, видимая отдача)

| День | Задача | Артефакт |
|------|--------|----------|
| 1–2 | Воспроизвести и fix booking на prod (HTMX target, auth, CSRF) | green P0-3 |
| 2 | Включить lab_head people/schedule templates **или** signed waver | green P0-13/14 |
| 2–3 | Выдать LAB_ADMIN, пройти staff checklist | green P0-7…10 |
| 3–4 | SMTP + test emails | green P0-15 |
| 4–5 | CSV pilot data + `generate_sessions` | green P0-16 |
| 5 | `pytest` + `smoke-test.sh` + backup | P0-18, 20, 17 |

## Неделя 2 (P1 polish)

- Mobile login + nav
- HTMX loading states
- Мини-расширение отчёта «записи»
- Student help page
- Go/no-go meeting с sign-off таблицей (Часть A)

---

# Часть H. Ключевые файлы (навигация)

| Тема | Путь |
|------|------|
| Бизнес-логика | `backend/apps/bookings/services/booking.py` |
| Окно слотов | `backend/apps/bookings/services/session_availability.py` |
| Scoping student | `backend/apps/academics/querysets.py` |
| Student web | `backend/apps/bookings/views/web.py` |
| Staff web | `backend/apps/bookings/views/staff.py` |
| Lab head | `backend/apps/bookings/views/lab_head.py` |
| Reports | `backend/apps/bookings/reports.py` |
| Settings | `backend/config/settings/base.py` |
| CSS | `backend/static/css/main.css` |
| Base layout | `backend/templates/base.html` |
| Student book | `backend/templates/bookings/book.html` |
| Staff bookings | `backend/templates/bookings/staff_bookings.html` |
| Lab head stubs | `backend/templates/bookings/lab_head/people.html`, `schedule.html` |
| Деканат stub | `backend/apps/integrations/dekanat.py` |
| Checklist | `docs/PILOT_ACCEPTANCE_CHECKLIST.md` |

---

# Часть I. Automated checks (перед GO)

```bash
cd backend
pytest apps/bookings/tests/test_booking.py -v
pytest apps/bookings/tests/test_student_scope.py -v
pytest apps/bookings/tests/test_staff_scope.py -v
pytest apps/bookings/tests/test_manual_booking.py -v
pytest apps/bookings/tests/test_lab_head_ui.py -v
pytest apps/bookings/tests/test_pilot_visibility.py -v
pytest
```

На VM:

```bash
bash scripts/run-tests-vm.sh
bash scripts/smoke-test.sh https://spmi-lab.ru
bash scripts/backup_db.sh
```

---

# Часть J. Тестовые аккаунты (аудит)

| Роль | Login | Password | Проверен на prod |
|------|-------|----------|------------------|
| Student | s210052@stud.spmi.ru | student123 | ✅ частично |
| Lab head | zavlab.pilot@spmi.ru | pilot123 | ✅ частично |
| LAB_ADMIN | — | — | ❌ |

---

*Документ собран из продуктово-технического аудита в Cursor (29.06.2026). Обновляйте статусы P0 при закрытии блокеров.*
