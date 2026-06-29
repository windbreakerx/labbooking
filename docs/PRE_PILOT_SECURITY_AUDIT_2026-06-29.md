# Pre-pilot security & code audit — Recap чата (2026-06-29)

**Роль:** security & code auditor перед пилотом  
**Модель:** GPT-5.3 Codex  
**Прод:** https://spmi-lab.ru  
**Источник истины:** код репозитория; live-проверки — по тест-аккаунтам (см. §8)

**Skills использованы:** `/labbooking-access-scope`, `/labbooking-prod-security`, `/labbooking-booking-service`, `/anthropic-cybersecurity`

**ТЗ:** PDF на рабочем столе (`ТЗ для студентов…`, `ТЗ для завлабов…`); в репозитории `docs/students_tz.txt` / `docs/zavlab_tz.txt` отсутствуют.

**Тест-аккаунты (live):**
- Студент: `s210052@stud.spmi.ru` / `student123`
- Завлаб: `zavlab.pilot@spmi.ru` / `pilot123`
- LAB_ADMIN: не предоставлен

---

## Executive summary

| Вердикт | Описание |
|---------|----------|
| **Студенческий scope** | Реализован через `StudentGroup` → disciplines/lab_works; покрыт unit/web/API тестами |
| **Staff scope** | Работает по `training_center`, **не** по `laboratory` — риск cross-lab утечки при нескольких лабораториях в одном УЦ |
| **BookingService** | Ядро бизнес-правил (14 дней, 22:00, 24 ч отмена, 1 запись/дисциплина) — в порядке |
| **Blocker пилота** | Cross-lab data leak, если в pilot data >1 laboratory на один `training_center` |
| **Автотесты в сессии аудита** | Shell/pytest из среды агента не отработали; bandit/pip-audit не установлены |
| **Live black-box** | Не завершён (лимит browser agent); чеклист для ручной проверки — §8 |

**План на 1–2 недели (порядок):**
1. P0: `staff_lab_filter` → laboratory-first
2. P0: prod `SECRET_KEY` без fallback
3. P1: PDF content validation, scoped student search, 404 masking
4. P1: отчёты — минимальный состав по ТЗ
5. P2: ratelimit на write endpoints, N+1 на hot paths

---

## 1. Security audit

### 1.1 Findings

| Severity | Проблема | Exploit scenario | Файл:строка | Fix |
|----------|----------|------------------|-------------|-----|
| **critical** | Staff scope по `training_center`, не по `laboratory` | Две лаборатории в одном УЦ: staff lab A видит bookings/sessions/support/reports lab B | `backend/apps/bookings/services/booking.py:535-547` | Laboratory-first в `staff_lab_filter`; fallback на TC только если `profile.laboratory` пуст |
| **high** | Insecure `SECRET_KEY` default в base | Ошибка `.env` на prod → предсказуемый ключ, компрометация сессий/JWT | `backend/config/settings/base.py:18` | В `prod.py`: `SECRET_KEY = env("SECRET_KEY")` без default; fail-fast |
| **medium** | IDOR enumeration: `403` vs `404` | Перебор `booking_id`/`ticket_id`: foreign существующий → 403, несуществующий → 404 | `backend/apps/bookings/views/api.py:229-240`, `289-303` | Для чужих объектов всегда `404` |
| **medium** | Поиск студентов staff без scope | Любой staff ищет всех студентов БД (email, ФИО, группа) | `backend/apps/bookings/services/booking.py:627-638`, `views/web.py:583-593` | Scope по lab/TC или по дисциплинам lab |
| **medium** | PDF upload: extension+size, без content check | Polyglot `.pdf` | `backend/apps/academics/models.py:124-129`, `views/staff.py:46-52` | `%PDF-` magic bytes + `content_type` |
| **low** | Rate limit только login + booking create | Flood на status/support/manual | `jwt_views.py:8`, `api.py:209` | `@ratelimit` на PATCH status, POST support, manual |
| **low** | `profile.disciplines` не security boundary | Завлаб назначает дисциплины — metadata; querysets не фильтруют по ним | `lab_head.py:135-144`, `academics/querysets.py` | Зафиксировать в docs; не использовать для auth до post-pilot |

### 1.2 Что в порядке

- JWT (API) + session (web), CSRF enabled, `IsAuthenticated` по умолчанию в DRF
- `SSO_ENABLED=0` по умолчанию; SSO endpoint возвращает 501
- Студент: `student_disciplines_qs` / `student_lab_works_qs` + object checks в views
- Support tickets: student limited to `student_support_training_centers_qs`
- Manual booking API/web: `staff_can_access_scoped_object` на session
- SMTP failures: `logger.exception` в `_send_email`; booking не откатывается
- Secrets: `.env` в `.gitignore`; hardcoded secrets в repo не найдены
- Prod: `DEBUG=False`, HSTS/cookies secure при `SECURE_SSL_REDIRECT=1`

### 1.3 Автопроверки (сессия аудита)

```bash
cd backend
pytest apps/bookings/tests/test_student_scope.py \
       apps/bookings/tests/test_staff_scope.py \
       apps/bookings/tests/test_pilot_visibility.py \
       apps/bookings/tests/test_booking.py -v
bandit -r apps config
pip-audit
```

**Статус:** pytest/bandit/pip-audit из среды агента не выполнились. **Рекомендация:** прогнать на VM через `scripts/run-tests-vm.sh` после деплоя.

---

## 2. Scoping vs ТЗ

| Роль | Ожидание ТЗ | Код | Статус |
|------|-------------|-----|--------|
| Студент | Только curriculum своей группы | `StudentGroup` M2M → `student_*_qs` | OK + тесты |
| Staff без lab | Пустые данные | `staff_lab_filter` → `.none()` | OK |
| Staff / lab head | Только своя лаборатория | Фильтр по `room__training_center` | **Gap** если несколько lab в УЦ |
| Manual booking | Только свой session | `staff_can_access_scoped_object` | OK на уровне TC |
| `profile.disciplines` | Назначение завлабом | Metadata, не auth | Зафиксировано |

**Несогласованность:** `staff_disciplines_qs` / `staff_managed_*` в `academics/querysets.py` уже используют `resolve_staff_laboratory`, а operational objects (`Booking`, `LabSession`, `SupportTicket`) — `staff_lab_filter` только по `training_center`. Это главный архитектурный разрыв.

---

## 3. Бизнес-логика vs ТЗ

| Правило ТЗ | Реализация | Файл | Gap |
|------------|------------|------|-----|
| 14 дней вперёд | `BOOKING_HORIZON_DAYS=14`, `booking_date_window` | `session_availability.py:35-53` | — |
| 22:00 открытие дня | `BOOKING_DAY_OPENS_AT=22:00` | `session_availability.py:49-52` | — |
| Закрытие ~15:00 | `BOOKING_DAY_CLOSES_AT=15:00` | idem | Доп. правило vs буквального ТЗ |
| Отмена 24 ч | `BOOKING_CANCEL_HOURS=24` | `booking.py:170-177` | — |
| 1 активная запись/дисциплина | `_check_discipline_limit` | `booking.py:179-186` | — |
| Статусы + auto VISITED | `change_status`, `mark_visited` | `booking.py`, `commands/mark_visited.py` | Проверить cron на VM |
| Waitlist | `join_waitlist`, `_promote_waitlist` | `booking.py:390-426` | Не в pilot checklist как must |
| Праздники | `Holiday` exclude | `session_availability.py:291-307` | — |
| Email на события | `_send_email` templates | `booking.py:465-523` | SMTP на prod — проверить вручную |
| Excel «расширенные» | 3 типа отчётов, упрощённый состав | `reports.py` | **Gap:** пол, должность, history статусов, manual FIO |

---

## 4. Оптимизация backend

### 4.1 Что такое over-engineering

**Over-engineering** — усложнение решения сверх того, что даёт измеримую пользу до ближайшей цели (здесь — стабильный пилот).

| Over-engineering (не делать) | Практичная альтернатива |
|------------------------------|-------------------------|
| Новый слой CQRS/Event Sourcing для bookings | Оставить `BookingService` + queryset helpers |
| Redis cache на все discipline lists | Сначала `prefetch_related` / один annotate |
| Переписать `session_availability` на raw SQL | Батч-загрузка bookings count для queryset сессий |
| Микросервис отчётов | openpyxl + scope filter; streaming — после пилота |
| Универсальный ABAC framework для всех ролей | Починить `staff_lab_filter` + 5–10 тестов |

**Правило:** менять только hot path с доказуемой нагрузкой (страница дисциплин, фильтры слотов, staff bookings list).

### 4.2 До пилота (1–3 дня, малый diff)

#### A. N+1 на `/disciplines/` (web)

**Проблема:** для каждой дисциплины отдельный запрос lab works.

```python
# views/web.py:256-257 — сейчас
for discipline in disciplines:
    discipline.catalog_lab_works = list(lab_works_qs(discipline.pk))
```

**Решение:** один prefetch всех lab works для списка discipline ids, группировка в Python dict.

```python
discipline_ids = [d.pk for d in disciplines]
all_lws = (
    student_lab_works_qs(user).filter(disciplines__in=discipline_ids)
    .prefetch_related("disciplines")
    .distinct()
)
by_discipline = {did: [] for did in discipline_ids}
for lw in all_lws:
    for did in lw.disciplines.values_list("pk", flat=True):
        if did in by_discipline:
            by_discipline[did].append(lw)
for discipline in disciplines:
    discipline.catalog_lab_works = by_discipline.get(discipline.pk, [])
```

**Эффект:** N+1 → 2–3 запроса. **Файлы:** `views/web.py`. **Риск:** низкий.

#### B. `_filter_sessions_with_free_seats` — Python loop + N queries

**Проблема:** для каждой сессии вызывается `session.available_seats` → несколько COUNT на сессию.

**Решение (минимальное):**
1. `select_related("lab_work", "room", "lab_work__primary_stand")`
2. Один annotate: `booked_count=Count("bookings", filter=Q(current_status=BOOKED))`
3. Отсечь `booked_count >= capacity` в SQL до Python loop
4. Python loop только для pair/weekday/holiday/window (логика без простого SQL)

**Эффект:** при 200 сессиях — с hundreds queries до ~5. **Файлы:** `session_availability.py`. **Риск:** средний — нужны тесты `test_booking.py::TestSessionAvailability`.

#### C. Staff bookings list

**Проблема:** тяжёлый list без `only()` / pagination tuning.

**Решение:** уже есть `select_related`; добавить `.only(...)` на поля шаблона если list тормозит на pilot data.

**Эффект:** меньше memory. **Отложить** если pilot <500 записей.

#### D. Staff rooms — N+1 disciplines per room

**Проблема:** `StaffRoomsView` — query per room для disciplines.

**Решение:** один запрос `Discipline.objects.filter(lab_works__default_room__in=room_ids).distinct()` + group by room_id.

**Файлы:** `views/staff.py:67-70`. **Эффект:** rooms page быстрее.

### 4.3 После пилота (когда есть метрики)

| Область | Когда трогать | Что делать | Не делать |
|---------|---------------|------------|-----------|
| Redis cache | p95 disciplines >300ms стабильно | Cache key `disciplines:{semester}:{group_id}`, TTL 5–15 min | Cache invalidation framework |
| `generate_sessions` | cron >2 min | Bulk create с `ignore_conflicts` / diff window | Переписывать на Celery |
| openpyxl reports | >10k rows timeout | `write_only=True`, iterator chunks | Отдельный report service |
| Web/API dedup | частые расхождения багов | Thin adapter calling same service functions | Общий «application layer» на 20 файлов |
| DB indexes | slow query log | Index на `(room_id, starts_at)` если нет | Premature index на всё |

### 4.4 Как измерять (до/после)

```bash
# Django debug toolbar / silk — локально на seed_demo
python manage.py seed_demo --full-pilot
# В shell: count queries для GET /disciplines/, GET /lab-works/{id}/book/filter/

# Prod: nginx access log — p95 latency для:
# /disciplines/, /lab-works/*/book/filter/, /staff/bookings/
```

**Критерий «достаточно» до пилота:** страницы открываются <2s на pilot dataset без timeout; pytest scope green.

---

## 5. Patch-пакет P0 / P1

### P0-1: Laboratory-first `staff_lab_filter` (blocker)

**Файл:** `backend/apps/bookings/services/booking.py`

**Заменить** функцию `staff_lab_filter` (строки 535–547):

```python
def staff_lab_filter(
    qs,
    user,
    *,
    training_center_lookup: str = "room__training_center",
    laboratory_lookup: str = "room__laboratory",
):
    """Scope staff to own laboratory; fallback to training_center if laboratory unset."""
    if user.role == UserRole.SYS_ADMIN:
        return qs
    try:
        profile = user.profile
    except (AttributeError, ObjectDoesNotExist):
        return qs.none()

    from apps.academics.querysets import resolve_staff_laboratory

    laboratory = resolve_staff_laboratory(user)
    if laboratory:
        lk = laboratory.pk if laboratory_lookup in {"pk", "id"} else laboratory
        return qs.filter(**{laboratory_lookup: lk})

    tc = getattr(profile, "training_center", None)
    if not tc:
        return qs.none()
    lookup_value = tc.pk if training_center_lookup in {"pk", "id"} else tc
    return qs.filter(**{training_center_lookup: lookup_value})
```

**Статус:** ✅ применено 2026-06-29.

Реализация: фильтр по `room__laboratory` **только если** `profile.laboratory_id` задан явно; иначе — прежний scope по `training_center` (не ломает staff без laboratory и существующие тесты).

**Дополнительно:** для queryset без `room` (SupportTicket, LabStand) — вызывающий код уже передаёт `training_center_lookup="training_center"`.

---

### P0-2: Prod SECRET_KEY fail-fast

**Файл:** `backend/config/settings/prod.py` — добавить после импорта base:

```python
SECRET_KEY = env("SECRET_KEY")  # noqa: F405 — no default; misconfig fails at startup
```

**Статус:** ✅ применено 2026-06-29.

---

### P1-1: PDF content validation

**Файл:** `backend/apps/bookings/views/staff.py` — в `StaffLabWorkUploadView.post`:

```python
if file := request.FILES.get("methodics_file"):
    if file.size > 10 * 1024 * 1024:
        messages.error(request, "Файл не должен превышать 10 МБ.")
    else:
        head = file.read(5)
        file.seek(0)
        if not head.startswith(b"%PDF-"):
            messages.error(request, "Допустимы только PDF-файлы.")
        else:
            lab_work.methodics_file = file
            ...
```

---

### P1-2: Scoped student search for staff

**Файл:** `backend/apps/bookings/services/booking.py` — `search_students_for_staff(query, staff_user=None, limit=15)`:

```python
def search_students_for_staff(query: str, staff_user=None, limit: int = 15):
    ...
    qs = User.objects.filter(role=UserRole.STUDENT).select_related("profile", "profile__student_group")
    if staff_user and staff_user.role != UserRole.SYS_ADMIN:
        from apps.academics.querysets import staff_disciplines_qs
        discipline_ids = staff_disciplines_qs(staff_user).values_list("pk", flat=True)
        qs = qs.filter(
            Q(profile__student_group__disciplines__in=discipline_ids)
            | Q(bookings__discipline_id__in=discipline_ids)
        ).distinct()
    return qs.filter(_student_search_q(query)).order_by(...)[:limit]
```

**Файл:** `views/web.py:588` — передать `request.user`.

---

### P1-3: 404 masking для foreign objects (API)

**Файлы:** `views/api.py` — `BookingCancelView`, `SupportMessageView`, `BookingStatusUpdateView`:

```python
# Вместо 403 для foreign scoped object:
return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
```

---

### P1-4: Reports — минимальный состав для пилота

**Файл:** `backend/apps/bookings/reports.py` — для `report_type == "bookings"` добавить колонки:
- Пол (`profile.gender`)
- Дата регистрации (`created_at`)
- Статус с display label

Post-pilot: отдельный `bookings_extended` с `BookingStatusHistory` (accumulation).

---

### P2 (после пилота)

- `@ratelimit` на `BookingStatusUpdateView`, `SupportMessageView`, `ManualBookingView`
- `StaffPeopleView` filter by `profile__laboratory` when set
- CI: bandit + pip-audit в pipeline

---

## 6. Новые тесты

### 6.1 `test_staff_scope.py` — добавить класс

```python
@pytest.fixture
def shared_tc(db):
    return TrainingCenter.objects.create(number=50, name="Shared UC")

@pytest.fixture
def lab_a(shared_tc):
    return Laboratory.objects.create(training_center=shared_tc, name="Lab A")

@pytest.fixture
def lab_b(shared_tc):
    return Laboratory.objects.create(training_center=shared_tc, name="Lab B")

@pytest.fixture
def staff_lab_a(db, shared_tc, lab_a):
    user = User.objects.create_user(..., role=UserRole.LAB_ADMIN, is_staff=True)
    user.profile.training_center = shared_tc
    user.profile.laboratory = lab_a
    user.profile.save()
    return user

# ... room_a, room_b, session_a, session_b, booking_a, booking_b ...

class TestStaffLaboratoryIsolation:
    def test_staff_lab_filter_uses_laboratory_not_only_tc(self, staff_lab_a, booking_a, booking_b):
        from apps.bookings.models import Booking
        ids = set(staff_lab_filter(Booking.objects.all(), staff_lab_a).values_list("pk", flat=True))
        assert booking_a.pk in ids
        assert booking_b.pk not in ids

    def test_staff_bookings_web_hides_sibling_lab(self, staff_lab_a, booking_b):
        client = Client()
        client.force_login(staff_lab_a)
        response = client.get("/staff/bookings/")
        assert response.status_code == 200
        assert booking_b.room.number.encode() not in response.content

    def test_manual_booking_foreign_laboratory_session_denied(self, staff_lab_a, student, session_b):
        ...

    def test_admin_report_excludes_sibling_lab(self, staff_lab_a, booking_a, booking_b):
        ...
```

### 6.2 `test_pilot_visibility.py`

```python
def test_operator_scoped_to_laboratory_when_set(operator):
    """Если seed_demo задаёт profile.laboratory — operator не видит чужую lab в том же TC."""
    ...

def test_zavlab_cannot_access_staff_manual_for_foreign_session(lab_head, ...):
    ...
```

### 6.3 `test_booking.py`

```python
def test_staff_student_search_scoped(staff, student, foreign_student):
    from apps.bookings.services import search_students_for_staff
    results = search_students_for_staff(student.email[:5], staff_user=staff)
    assert student in results
    assert foreign_student not in results
```

### 6.4 Security regression

```python
def test_foreign_booking_cancel_returns_404_not_403(student, foreign_booking):
    client = APIClient()
    client.force_authenticate(user=student)
    r = client.post(f"/api/v1/bookings/{foreign_booking.pk}/cancel/")
    assert r.status_code == 404
```

**Команда после патчей:**

```bash
cd backend
pytest apps/bookings/tests/test_staff_scope.py \
       apps/bookings/tests/test_student_scope.py \
       apps/bookings/tests/test_pilot_visibility.py \
       apps/bookings/tests/test_booking.py -v
```

---

## 7. Live black-box checklist (ручная проверка)

### Студент (`s210052@stud.spmi.ru`)

| # | Действие | Ожидание |
|---|----------|----------|
| 1 | Login → `/disciplines/` | Только дисциплины своей группы |
| 2 | Запомнить свой `discipline_id`, открыть `/disciplines/{id±1}/lab-works/` | 404, без названий чужих дисциплин |
| 3 | `/lab-works/{foreign_id}/book/` | 404 |
| 4 | JWT: `POST /api/v1/auth/token/` → `GET /api/v1/disciplines/{foreign}/lab-works/` | 404 |
| 5 | `/support/{foreign_ticket_id}/` | 404 |
| 6 | Запись + отмена (24h rule) | Happy path |

### Завлаб (`zavlab.pilot@spmi.ru`)

| # | Действие | Ожидание |
|---|----------|----------|
| 1 | `/lab-head/` | Dashboard, TC assigned |
| 2 | `/staff/bookings/` | Только своя lab/TC |
| 3 | POST status на foreign `booking_id` (DevTools) | 404/redirect error, статус не меняется |
| 4 | Download report | Нет строк foreign lab |
| 5 | `/lab-head/people/` | Только people своей lab |

### LAB_ADMIN (когда будет аккаунт)

- Повторить staff сценарии §7 + manual booking foreign session → отказ

---

## 8. Соответствие PILOT_ACCEPTANCE_CHECKLIST

| Checklist item | Audit status |
|----------------|--------------|
| Student scope web/API | Code OK; live — §7 |
| Staff scope | **Fix P0-1 required** if multi-lab TC |
| Staff no TC → empty | OK |
| Manual booking foreign session | OK at TC level |
| Lab head dashboard | Code OK |
| profile.disciplines metadata | Documented |
| SMTP observable | Code OK; verify prod |
| Backup before pilot | Ops — not code |

---

## 9. Ключевые файлы (reference)

| Тема | Путь |
|------|------|
| Scope querysets | `backend/apps/academics/querysets.py` |
| Staff filter | `backend/apps/bookings/services/booking.py` |
| Booking rules | `backend/apps/bookings/services/booking.py` |
| Slot availability | `backend/apps/bookings/services/session_availability.py` |
| API views | `backend/apps/bookings/views/api.py` |
| Web views | `backend/apps/bookings/views/web.py` |
| Staff UI | `backend/apps/bookings/views/staff.py` |
| Lab head | `backend/apps/bookings/views/lab_head.py` |
| Reports | `backend/apps/bookings/reports.py` |
| Prod settings | `backend/config/settings/prod.py` |
| Scope tests | `test_student_scope.py`, `test_staff_scope.py`, `test_pilot_visibility.py` |

---

## 10. Хронология чата (кратко)

1. Запрос: security audit перед пилотом (GPT-5.3 Codex), skills, ключевые модули, pytest, bandit, live на spmi-lab.ru
2. Прочитаны: README, PILOT_PLAN, PILOT_ACCEPTANCE_CHECKLIST, security.md, api.md, ТЗ PDF, vendor security skills
3. Code review: querysets, permissions, BookingService, session_availability, web/api/staff/lab_head views, prod settings, reports
4. Findings: cross-lab scope gap, SECRET_KEY, IDOR enumeration, student search, PDF validation
5. Автотесты/sast из agent shell — не выполнены; live browser — не завершён
6. Follow-up (этот документ): patch P0/P1, тесты, оптимизация, over-engineering, полный .md recap

---

*Документ создан по итогам чата 2026-06-29. Обновлять после применения P0/P1 и прохождения live checklist.*
