# Фаза 1 gap-closure: изменения от 29.06.2026

> Сессия: gap-анализ СПГУ → закрытие P0 (G-028, G-016) → CSV-документация → fix регрессий pytest на VM.  
> Связанные документы: [GAP_ANALYSIS_SPGU_2026-06-29.md](GAP_ANALYSIS_SPGU_2026-06-29.md), [csv_templates/README.md](csv_templates/README.md), [PILOT_DATA_SETUP.md](PILOT_DATA_SETUP.md).

---

## Краткое резюме

| Gap ID | Статус | Суть |
|--------|--------|------|
| **G-028** | ✅ Закрыт | Scoping списка «Люди» staff/lab-head по `profile.laboratory`, не только по УЦ |
| **G-016** | ✅ Закрыт | Восстановлены HTMX-шаблоны `lab_head/people.html` и `lab_head/schedule.html` |
| **CSV** | ✅ Документирован | README для `docs/csv_templates/` + ссылки в PILOT_DATA_SETUP и gap-анализе |
| **Staff bookings UI** | ✅ Fix | Номер аудитории в списке записей staff (регрессия тестов scoping) |
| **Student slot picker** | ✅ Fix test | `room.capacity=1` в тесте пересечения слотов в одной аудитории |

**Не входит в эту фазу (следующие шаги):** G-001 Faculty, G-008 TEACHER read-only, G-009 матрица LAB_ADMIN, G-029 полный API-audit.

---

## 1. G-028 — scoping staff people по лаборатории

### Проблема

`StaffPeopleView` фильтровал пользователей только по `profile.training_center`. В одном УЦ несколько лабораторий — staff lab A видел сотрудников lab B.

### Решение

Общая функция `staff_people_qs(user)` в queryset-слое:

- `SYS_ADMIN` — все `LAB_ADMIN` + `TEACHER`
- при `profile.laboratory` — только люди **этой** лаборатории
- иначе — fallback по `training_center` (legacy-поведение)

### Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `backend/apps/academics/querysets.py` | Новая функция `staff_people_qs()` |
| `backend/apps/bookings/services/lab_head.py` | `lab_head_people_qs()` → делегирует в `staff_people_qs()` + prefetch дисциплин |
| `backend/apps/bookings/views/staff.py` | `StaffPeopleView.get_queryset()` → `staff_people_qs()` |
| `backend/templates/bookings/staff/people.html` | Колонка «Лаборатория»: имя lab или «УЦ №N» |
| `backend/apps/bookings/tests/test_staff_scope.py` | Тест `test_staff_people_hides_sibling_laboratory` |

### Поведение scoping (без изменений)

- Студенты: `student_group` → учебный план
- Записи/bookings: `staff_lab_filter` по `room__laboratory`
- Support tickets: только `training_center`

---

## 2. G-016 — Lab Head UI (people + schedule)

### Проблема

Backend и POST-обработчики существовали; шаблоны показывали заглушку «На доработке».

### `lab_head/people.html`

- Таблица: ФИО, email, роль, привязанные дисциплины
- Диалог «Добавить» → `POST /lab-head/people/create/`
- Кнопка «Привязки» → `POST /lab-head/people/<pk>/bindings/` с чекбоксами дисциплин
- Предзаполнение чекбоксов из `data-discipline-ids` на кнопке

### `lab_head/schedule.html`

- Таблица `schedule_rows`: ЛР, ауд., день, время, чётность, места, длительность, преподаватель
- Диалог «Добавить запись» → `POST /lab-head/schedule/create/`
- Если нет активного семестра — сообщение вместо формы

### Тесты

| Файл | Тест |
|------|------|
| `backend/apps/bookings/tests/test_lab_head_ui.py` | `test_lab_head_people_page_renders` — нет «На доработке», виден email staff |
| `backend/apps/bookings/tests/test_lab_head_ui.py` | `test_lab_head_schedule_page_renders` — нет заглушки, есть заголовок |

---

## 3. CSV-шаблоны

Шаблоны `pilot_*.csv` уже были в `docs/csv_templates/`. Добавлена документация:

| Файл | Содержание |
|------|------------|
| `docs/csv_templates/README.md` | Порядок импорта, описание колонок всех 8 файлов, план `spgu_*.csv` после модели Faculty |
| `docs/PILOT_DATA_SETUP.md` | Ссылка на README |
| `docs/GAP_ANALYSIS_SPGU_2026-06-29.md` | Gap-анализ + ссылка на CSV README |

### Команда импорта (на VM)

```bash
cd ~/labbooking
bash scripts/run-tests-vm.sh   # после деплоя — проверка

# Импорт данных (из backend/ или через docker exec)
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_groups.csv --type=groups
# … см. PILOT_DATA_SETUP.md
```

---

## 4. Fix регрессий pytest (141 tests, VM)

После прогона `bash scripts/run-tests-vm.sh` упали 3 теста (138 passed). **Не связаны с G-028.**

### 4.1 Staff bookings — номер аудитории в HTML

**Тесты:**

- `TestStaffLaboratoryIsolation.test_staff_bookings_web_hides_sibling_laboratory`
- `TestStaffLaboratoryScopeRegression.test_bookings_visible_when_room_laboratory_unassigned`

**Причина:** `staff_bookings.html` не выводил `room.number` — queryset был верный, HTML — нет.

**Fix:** `backend/templates/bookings/staff_bookings.html`

- Мобильная карточка: блок «Аудитория» (`№{{ b.room.number }} · УЦ №…`)
- Десктоп-таблица: колонка «Ауд.» + sortable `room`

### 4.2 Student — выбор earliest slot в паре

**Тест:** `TestStudentScopeWeb.test_book_filter_auto_picks_earliest_slot_in_pair`

**Причина:** fixture `room` с `capacity=5`. При blocking-брони на 14:15–15:00 пересекающиеся слоты 14:15 и 14:45 оставались «свободными» (capacity-based логика из PILOT). Выбирался pk раннего слота, тест ждал 15:00.

**Fix:** `backend/apps/bookings/tests/test_student_scope.py` — в начале теста:

```python
room.capacity = 1
room.save(update_fields=["capacity"])
```

---

## 5. Прогон тестов на VM

На хосте VM **нет** `pytest` — используйте скрипт:

```bash
cd ~/labbooking
git pull

# Только затронутые тесты
bash scripts/run-tests-vm.sh \
  apps/bookings/tests/test_staff_scope.py \
  apps/bookings/tests/test_lab_head_ui.py \
  apps/bookings/tests/test_student_scope.py -v

# Полный пилотный набор (~141 test)
bash scripts/run-tests-vm.sh
```

Скрипт: проверяет `.env` и контейнер `web`, ставит `requirements-dev.txt`, запускает pytest с `DJANGO_SETTINGS_MODULE=config.settings.test`.

---

## 6. Предупреждения Django 6.0 (не блокер)

```
RemovedInDjango60Warning: CheckConstraint.check is deprecated in favor of .condition.
```

Затронуты:

- `apps/academics/models.py` (~164)
- `apps/scheduling/models.py` (~235)
- миграции `0007_lab_work_stand_and_duration_constraints`, `0005_schedule_duration_constraints`

Отдельный PR: заменить `check=` на `condition=` в моделях; миграции — по необходимости.

---

## 7. Полный список изменённых файлов

```
backend/apps/academics/querysets.py
backend/apps/bookings/services/lab_head.py
backend/apps/bookings/views/staff.py
backend/templates/bookings/staff/people.html
backend/templates/bookings/staff_bookings.html
backend/templates/bookings/lab_head/people.html
backend/templates/bookings/lab_head/schedule.html
backend/apps/bookings/tests/test_staff_scope.py
backend/apps/bookings/tests/test_lab_head_ui.py
backend/apps/bookings/tests/test_student_scope.py
docs/GAP_ANALYSIS_SPGU_2026-06-29.md
docs/csv_templates/README.md
docs/PILOT_DATA_SETUP.md
docs/CHANGELOG_GAP_PHASE1_2026-06-29.md   ← этот файл
```

---

## 8. Следующие шаги (фаза 2)

| Приоритет | Gap | Задача |
|-----------|-----|--------|
| 1 | G-001–003 | Модель `Faculty`, FK на `Department` / `StudentGroup`, `Laboratory.faculty` |
| 2 | G-008 | `TEACHER` — только просмотр записей |
| 3 | G-009, G-010 | Матрица LAB_ADMIN vs LAB_HEAD; scoping по аудиториям |
| 4 | G-029 | Финальный API-audit (если pytest зелёный — точечных дыр нет) |

### Промпт для следующего чата

```
@docs/GAP_ANALYSIS_SPGU_2026-06-29.md
@docs/CHANGELOG_GAP_PHASE1_2026-06-29.md

pytest на VM зелёный. Фаза 1 закрыта.

Реализуй эпик E1 — модель Faculty:
- Faculty(code, title, ordering)
- Department.faculty FK + data migration backfill
- StudentGroup.department FK (nullable)
- Laboratory.faculty + lab_type (REGULAR / INTERDEPARTMENTAL / COMPLEX)
- generate_lab_work_code() из department→faculty
- тесты + обновление seed_demo для НГФ

Не ломать scoping student_group / laboratory. HTMX only.
```

---

## 9. Связанные документы

- [GAP_ANALYSIS_SPGU_2026-06-29.md](GAP_ANALYSIS_SPGU_2026-06-29.md) — полный gap-анализ и эпики
- [LAB_HEAD_UI_EXPLAINED.md](LAB_HEAD_UI_EXPLAINED.md) — архитектура кабинета завлаба
- [PILOT_DATA_SETUP.md](PILOT_DATA_SETUP.md) — наполнение данных пилота
- [csv_templates/README.md](csv_templates/README.md) — контракт CSV-колонок
