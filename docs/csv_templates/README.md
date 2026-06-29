# CSV-шаблоны для import_dekanat_csv

Команда: `python manage.py import_dekanat_csv <файл> --type=<тип>`

Кодировка по умолчанию: `utf-8-sig`. Разделитель: запятая.

## Порядок импорта

1. `seed_demo` (или вручную: семестр, УЦ, аудитории, лаборатории, ЛР из Excel)
2. `groups` — учебные группы
3. `disciplines` — дисциплины активного семестра
4. `lab_bindings` — привязка дисциплин/ЛР к УЦ
5. `curriculum` — учебный план: группа → дисциплина
6. `staff` — завлаб и сотрудники
7. `teachers` — преподаватели
8. `staff_bindings` — дисциплины сотрудников/преподавателей
9. `students` — студенты

Пример полной цепочки — [PILOT_DATA_SETUP.md](../PILOT_DATA_SETUP.md).

## Файлы и колонки

### pilot_groups.csv (`--type=groups`)

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| `name` | да | Название группы (уникальное) |
| `faculty` | нет | Факультет (строка, до появления модели Faculty) |
| `dekanat_id` | нет | ID в Деканате |

### pilot_disciplines.csv (`--type=disciplines`)

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| `title` | да | Название дисциплины |
| `code` | нет | Код (уникальный ключ при update) |
| `dekanat_id` | нет | ID в Деканате |
| `description` | нет | Описание |
| `is_published` | нет | `1`/`0`, `да`/`нет` (по умолчанию опубликовано) |
| `training_center_number` | нет | Номер УЦ для M2M-привязки |

Флаг `--semester` задаёт семестр (по умолчанию «Пилот 2026/2027 (нефтегаз)»).

### pilot_curriculum.csv (`--type=curriculum`)

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| `group_name` | да | Имя группы из `groups` |
| `discipline_code` | да | Код дисциплины |

Одна строка = одна дисциплина в учебном плане группы.

### pilot_lab_bindings.csv (`--type=lab_bindings`)

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| `discipline_code` | да | Код дисциплины |
| `training_center_number` | да | Номер УЦ |
| `lab_work_number` | нет | Номер ЛР; если пусто — привязка всех ЛР дисциплины |

### pilot_staff.csv (`--type=staff`)

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| `email` | да* | Email (*если пуст — генерируется `@demo.local`) |
| `password` | нет | Пароль (по умолчанию из `--default-password`) |
| `last_name` | да | Фамилия |
| `first_name` | да | Имя |
| `role` | нет | `LAB_ADMIN`, `LAB_HEAD`, `SYS_ADMIN` |
| `training_center_number` | нет | УЦ для профиля |
| `is_staff` | нет | Django `is_staff` |
| `discipline_codes` | нет | Коды дисциплин через запятую |

> После появления модели `Laboratory` в импорт будет добавлена колонка `laboratory_name` для scoping staff по лаборатории.

### pilot_teachers.csv (`--type=teachers`)

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| `email` | да* | Email |
| `password` | нет | Пароль |
| `last_name` | да | Фамилия |
| `first_name` | да | Имя |
| `training_center_number` | нет | УЦ |
| `is_staff` | нет | Django `is_staff` |
| `discipline_codes` | нет | Коды дисциплин |

### pilot_staff_bindings.csv (`--type=staff_bindings`)

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| `email` | да | Email существующего пользователя |
| `discipline_codes` | да | Коды дисциплин через запятую |

### pilot_students.csv (`--type=students`)

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| `email` | да* | Email |
| `password` | нет | Пароль |
| `last_name` | да | Фамилия |
| `first_name` | да | Имя |
| `group` | нет | Имя группы → `UserProfile.student_group` |
| `student_id` | нет | ID студента |
| `dekanat_id` | нет | ID в Деканате |
| `faculty` | нет | Факультет (строка) |
| `gender` | нет | `M` / `F` |
| `phone` | нет | Телефон |

## Планируемые шаблоны (эпик E1 — организационная модель)

После введения `Faculty` и `Department.faculty`:

- `spgu_faculties.csv` — справочник факультетов
- `spgu_departments.csv` — кафедры с `faculty_code`
- `spgu_laboratories.csv` — лаборатории: `name`, `training_center_number`, `faculty_code`, `lab_type`

Импорт будет расширен отдельными `--type`; текущие pilot_* файлы останутся для НГФ-пилота.

## Проверка после импорта

```bash
cd backend
pytest apps/bookings/tests/test_pilot_visibility.py apps/bookings/tests/test_student_scope.py -v
```
