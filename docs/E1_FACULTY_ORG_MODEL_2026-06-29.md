# E1: Организационная модель СПГУ — Faculty, Department, Laboratory

> Дата: 29.06.2026  
> Контекст: эпик E1 из [GAP_ANALYSIS_SPGU_2026-06-29.md](GAP_ANALYSIS_SPGU_2026-06-29.md)  
> Предусловие: фаза 1 закрыта (G-028, G-016, CSV README); pytest на VM — 141 passed.

---

## 1. Цель эпика

Ввести организационную иерархию **Faculty → Department → StudentGroup** и привязку **Laboratory → Faculty + тип лаборатории**, не ломая:

- scoping студентов по M2M учебного плана (`StudentGroup.disciplines`, `StudentGroup.lab_works`);
- scoping staff/lab-head по `UserProfile.laboratory` / `training_center`;
- существующие CSV-импорты и CharField `faculty` на группах и профилях.

Это **пилотный каркас для НГФ** (1 факультет, 3 кафедры, 1 комплексная лаборатория), а не полный каталог 8+1 факультетов СПГУ — он запланирован в эпике E9.

---

## 2. Изменения в моделях данных

### 2.1. `Faculty` (`apps/academics/models.py`)

Новая модель справочника факультетов:

| Поле | Тип | Описание |
|------|-----|----------|
| `code` | `CharField(16)`, unique | Короткий код, напр. `НГФ` |
| `title` | `CharField(256)` | Полное название |
| `ordering` | `PositiveIntegerField` | Порядок в списках |

Meta: `ordering = ["ordering", "title"]`.

**Что сознательно не делали:**

- Не заменяли CharField `StudentGroup.faculty` и `UserProfile.faculty` на FK — CSV/Деканат и старые данные продолжают работать со строкой.
- Не добавляли модель «Университет» — по-прежнему подразумевается один вуз.

### 2.2. `Department.faculty`

`Department` получил nullable FK:

```python
faculty = models.ForeignKey(
    Faculty,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="departments",
)
```

Все существующие кафедры (в т.ч. три из migration `0008_department`) после миграции привязаны к НГФ.

### 2.3. `StudentGroup.department`

`StudentGroup` получил nullable FK на кафедру:

```python
department = models.ForeignKey(
    "Department",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="student_groups",
)
```

Поле `faculty` (CharField) **сохранено** для обратной совместимости с `import_dekanat_csv` и pilot CSV.

**Scoping студентов не изменился:** `apps/academics/querysets.py` по-прежнему фильтрует по M2M учебного плана, не по `department` или `faculty`.

### 2.4. `Laboratory.faculty` и `Laboratory.lab_type` (`apps/scheduling/models.py`)

```python
class LaboratoryType(models.TextChoices):
    REGULAR = "REGULAR", "Кафедральная"
    INTERDEPT = "INTERDEPT", "Межкафедральная"
    COMPLEX = "COMPLEX", "Комплексная"
```

| Поле | Тип | Описание |
|------|-----|----------|
| `faculty` | FK → `academics.Faculty`, nullable | Организационная принадлежность |
| `lab_type` | `CharField`, default `REGULAR` | Тип лаборатории |

**Scoping staff/lab-head не изменился:** фильтрация по `profile.laboratory` и `training_center`.

**Что сознательно не делали:**

- M2M `Laboratory ↔ Faculty` для межкафедральных лабораторий (упомянуто в G-004 как следующий шаг).

---

## 3. Миграции

### 3.1. `academics/migrations/0011_faculty.py`

1. Создаёт таблицу `Faculty`.
2. Добавляет `Department.faculty` и `StudentGroup.department` (nullable).
3. RunPython `populate_faculty_and_links`:
   - создаёт факультет **НГФ** (`code=НГФ`, `title=Нефтегазовый факультет`, `ordering=0`);
   - проставляет `Department.faculty_id = НГФ` для всех кафедр без faculty.

### 3.2. `scheduling/migrations/0007_laboratory_faculty.py`

Зависит от `academics.0011_faculty`.

1. Добавляет `Laboratory.faculty` и `Laboratory.lab_type` (default `REGULAR`).
2. RunPython `backfill_laboratory_faculty`:
   - всем лабораториям без faculty — `faculty_id` НГФ;
   - лабораториям с подстрокой «комплексн» в `name` (case-insensitive) — `lab_type=COMPLEX`.

**На существующей VM-БД достаточно:**

```bash
bash scripts/deploy-vm.sh
# внутри: python manage.py migrate --noinput
```

---

## 4. `generate_lab_work_code()` — G-025

Файл: `apps/bookings/services/lab_head.py`.

### Было

```python
faculty_code = "НГФ"  # hardcode
# department_code и discipline_code — из department/discipline
```

### Стало

Цепочка для кода факультета:

```
discipline → department → faculty.code
```

Алгоритм:

1. `faculty_code` — из `discipline.department.faculty.code` (нормализация `_normalize_short_code`);
2. `department_code` — `department.short_code` или инициалы из `department.title`;
3. `discipline_code` — `discipline.short_code` или инициалы из `discipline.title`;
4. формат: `{faculty}-{dept}-{disc}-{number}`;
5. при коллизии — суффикс `-2`, `-3`, …

### Fallback (без department/faculty)

| Компонент | Значение |
|-----------|----------|
| faculty | `НГФ` |
| department | `БК` |
| discipline | `ДИС` |

Это сохраняет поведение существующих тестов lab-head (`code.startswith("НГФ-")`) для дисциплин без кафедры.

Примеры:

| Условие | Код |
|---------|-----|
| department `БС`, faculty `НГФ`, discipline `БУ`, number=1 | `НГФ-БС-БУ-1` |
| discipline без department, short_code `ОД`, number=2 | `НГФ-БК-ОД-2` |
| discipline=None, number=3 | `НГФ-БК-ДИС-3` |

---

## 5. Django Admin

| Модель | Изменения |
|--------|-----------|
| `Faculty` | Новый `FacultyAdmin`: `code`, `title`, `ordering` |
| `Department` | В list_display/list_filter добавлен `faculty` |
| `StudentGroup` | В list_display/list_filter добавлен `department` |
| `Laboratory` | В list_display/list_filter добавлены `faculty`, `lab_type` |

---

## 6. `seed_demo` — пилот НГФ

Файл: `apps/bookings/management/commands/seed_demo.py`.

### При любом запуске (в т.ч. без `--full-pilot`)

Метод `_ensure_ngf_faculty()` создаёт/обновляет справочник НГФ.

`_ensure_infrastructure()`:

- УЦ №1 и комплексная лаборатория НГФ;
- лаборатория: `faculty=НГФ`, `lab_type=COMPLEX`;
- при повторном запуске принудительно обновляет `faculty` и `lab_type`, если они сбились.

### Только с `--full-pilot`

1. Три кафедры НГФ с `faculty=НГФ` и `ordering`.
2. Группы `ТНГ-24`, `ГРП-24`, `ЭХТ-24`, `НГС-18-2`:
   - `faculty="Нефтегазовый"` (CharField, как раньше);
   - `department` — по карте `group_department_map`.
3. Дисциплины, ЛР, студенты, слоты — без изменения логики scoping.

**Важно для деплоя:**

- `bash scripts/deploy-vm.sh --import-data` вызывает `seed_demo` **без** `--full-pilot` → завлаб/сотрудники + инфраструктура с faculty на лаборатории; группы с `department` **не** создаются этим путём.
- Полный пилот с группами и department:

  ```bash
  docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web \
    python manage.py seed_demo --full-pilot
  ```

---

## 7. Тесты

Новый файл: `apps/academics/tests/test_faculty.py` (8 тестов).

| Класс | Что проверяет |
|-------|---------------|
| `TestFacultyModel` | ordering, `__str__`, связь Department↔Faculty |
| `TestFacultyModel` | `StudentGroup.department` nullable и установка FK |
| `TestLaboratoryFaculty` | `Laboratory.faculty` + `lab_type=COMPLEX` |
| `TestGenerateLabWorkCode` | код из цепочки department→faculty |
| `TestGenerateLabWorkCode` | fallback без department |
| `TestGenerateLabWorkCode` | суффикс при коллизии кодов |
| `TestGenerateLabWorkCode` | defaults при `discipline=None` |

**Не входят в pilot-набор** `scripts/run-tests-vm.sh` по умолчанию — см. раздел 9.

Существующие тесты scoping и lab-head UI **не менялись** и должны оставаться зелёными.

---

## 8. Закрытые и частично закрытые gaps

См. [GAP_ANALYSIS_SPGU_2026-06-29.md](GAP_ANALYSIS_SPGU_2026-06-29.md).

### Фаза 1 (до E1)

| Gap | Описание | Статус |
|-----|----------|--------|
| **G-028** | Staff people scoped по laboratory, не по УЦ | Закрыт |
| **G-016** | UI `lab_head/people.html`, `schedule.html` | Закрыт |
| CSV README | Документация шаблонов и порядка импорта | Закрыт |

### Эпик E1

| Gap | Было | Стало | Статус |
|-----|------|-------|--------|
| **G-001** | Нет модели Faculty | Справочник + backfill НГФ; CharField сохранён | **Частично** — полный каталог 8+1 → E9 |
| **G-002** | Department без faculty | FK + backfill на НГФ | **Закрыт для пилота** |
| **G-003** | StudentGroup без department | FK nullable; seed `--full-pilot` | **Частично** — CSV/import без `department_code` |
| **G-004** | Laboratory только → УЦ | `faculty_id`, `lab_type` | **Частично** — один FK; M2M межкафедр. → позже |
| **G-025** | Hardcode `НГФ` в коде ЛР | Код из department→faculty + fallback | **Закрыт для пилота** |
| **G-026** | 3 кафедры без faculty | Привязаны к НГФ | **Частично** — полный каталог → E9 |
| **G-027** | 1 lab без org-метаданных | `faculty=НГФ`, `lab_type=COMPLEX` | **Частично** — ~27 лабораторий → E9 |

### Не входило в E1

Роли TEACHER/LAB_ADMIN (G-008, G-009), scoping по аудитории (G-010), M2M room/stand (G-012–G-015), approval workflow (G-011), LAB_DIRECTOR (G-005), интеграция Деканат (G-031) и др.

---

## 9. Деплой и тесты на VM

### Деплой

```bash
# из корня репозитория на VM
bash scripts/deploy-vm.sh
```

Скрипт: build → migrate (применит `0011` и `0007`) → collectstatic → smoke test.

С импортом Excel (завлаб + Excel, без full-pilot групп):

```bash
bash scripts/deploy-vm.sh --import-data
```

### Тесты

```bash
# pilot regression (6 файлов, без test_faculty.py)
bash scripts/run-tests-vm.sh

# новые тесты E1
bash scripts/run-tests-vm.sh apps/academics/tests/test_faculty.py -v

# весь pytest
bash scripts/run-tests-vm.sh --full -v
```

Ожидаемый счёт после E1: **141 + 8 = 149 passed** (если регрессий нет).

### Sanity-check в shell после migrate

```python
from apps.academics.models import Faculty, Department, StudentGroup
from apps.scheduling.models import Laboratory

ngf = Faculty.objects.get(code="НГФ")
assert Department.objects.filter(faculty__isnull=True).count() == 0

lab = Laboratory.objects.filter(name__icontains="комплексн").first()
assert lab.faculty.code == "НГФ"
assert lab.lab_type == "COMPLEX"

# > 0 только после seed_demo --full-pilot
StudentGroup.objects.filter(department__isnull=False).count()
```

---

## 10. Список изменённых файлов

| Файл | Суть |
|------|------|
| `backend/apps/academics/models.py` | `Faculty`; FK на `Department`, `StudentGroup` |
| `backend/apps/academics/migrations/0011_faculty.py` | Схема + backfill НГФ |
| `backend/apps/academics/admin.py` | `FacultyAdmin`; поля в Department/StudentGroup |
| `backend/apps/academics/tests/test_faculty.py` | 8 unit-тестов |
| `backend/apps/academics/tests/__init__.py` | Пакет тестов |
| `backend/apps/scheduling/models.py` | `LaboratoryType`; FK faculty, lab_type |
| `backend/apps/scheduling/migrations/0007_laboratory_faculty.py` | Схема + backfill |
| `backend/apps/scheduling/admin.py` | Поля faculty, lab_type в LaboratoryAdmin |
| `backend/apps/bookings/services/lab_head.py` | `generate_lab_work_code()` из department→faculty |
| `backend/apps/bookings/management/commands/seed_demo.py` | НГФ faculty, lab metadata, department на группах (--full-pilot) |

---

## 11. Следующие шаги (вне E1)

1. **E9** — полный каталог факультетов/кафедр/лабораторий; CSV `spgu_faculties.csv`, `spgu_departments.csv`, `spgu_laboratories.csv`.
2. Расширить `import_dekanat_csv`: колонка `department_code` / `faculty_code` для групп.
3. Добавить `apps/academics/tests/test_faculty.py` в `PILOT_TESTS` в `scripts/run-tests-vm.sh` (опционально).
4. M2M faculty для межкафедральных лабораторий (G-004).
5. Постепенный отказ от CharField `faculty` на группах — только после миграции всех импортов.

---

## Связанные документы

- [GAP_ANALYSIS_SPGU_2026-06-29.md](GAP_ANALYSIS_SPGU_2026-06-29.md)
- [csv_templates/README.md](csv_templates/README.md)
- [ROADMAP.md](ROADMAP.md)
- Skill: `.cursor/skills/labbooking-access-scope/SKILL.md`
