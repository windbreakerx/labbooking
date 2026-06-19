# Пилот: сценарий и данные (пункт 1)

Документ фиксирует минимальный рабочий скоуп пилота и способ наполнения БД без SSO и без полного staff UI.

## 1) Скоуп пилота

- 1 лаборатория: `TrainingCenter` №1 "Комплексная учебная лаборатория нефтегазового факультета".
- 15 аудиторий, включая `1123` (10 мест) и `2105` (21 место) для ключевых ЛР.
- 3 кафедры нефтегазового факультета.
- 31 дисциплина (все из согласованного списка кафедр).
- ЛР:
  - детализированные ЛР для дисциплин `Ремонт и обслуживание газонефтепроводов` и `Эксплуатация сетей газораспределения и газопотребления`;
  - отдельная ЛР по буримости для дисциплины `Техника и технология бурения нефтяных и газовых скважин` (ауд. `2105`);
  - по остальным дисциплинам — по 1 пилотной ЛР.
- Персонал: 1 завлаб (`LAB_HEAD`) + 2 сотрудника (`LAB_ADMIN`) и 4 преподавателя (`TEACHER`).
- Студенты: 90 (группы `ТНГ-24`, `ГРП-24`, `ЭХТ-24`, `НГС-18-2`).
- Слоты: на 2 недели вперёд (по умолчанию), масштабируемо через `--weeks`.

## 2) Минимальный набор сущностей в БД

- `Semester`: 1 активный семестр пилота.
- `TrainingCenter`: 1 запись.
- `Room`: 15 записей.
- `StudentGroup`: 4 записи с учебными планами по кафедрам.
- `Discipline`: 31 запись, привязанная к лаборатории №1.
- `LabWork`: 36 записей (детализированные ЛР для 3 дисциплин + базовые ЛР остальных дисциплин), привязанные к лаборатории №1.
- `LabSession`: минимум 72 открытых слота при `--weeks 2`.
- `User`:
  - 1 завлаб (`LAB_HEAD`);
  - 2 сотрудника лаборатории (`LAB_ADMIN`);
  - 4 преподавателя (`TEACHER`);
  - 90 студентов (`STUDENT`).
- `UserProfile`:
  - для студентов: `student_group`, `group_name`, `student_id`, `dekanat_id`;
  - для сотрудников/преподавателей/завлаба: `training_center`, опционально `disciplines`.
- `Holiday`: 1 запись (тест обработки праздников).

### Матрица учебных планов (seed_demo)

| Группа | Кафедра / дисциплины |
|--------|----------------------|
| `ТНГ-24`, `ГРП-24` | Кафедра транспорта и хранения нефти и газа (NGF-001 … NGF-011) |
| `ЭХТ-24` | Кафедра разработки и эксплуатации месторождений (NGF-025 … NGF-031) |
| `НГС-18-2` | Кафедра бурения скважин (NGF-012 … NGF-024) |

## 3) Чем наполняем: seed_demo, CSV или admin

Решение для пилота: **комбинированный подход**.

- `seed_demo` — основной канал для согласованного набора пилотных данных нефтегазового факультета (группы, учебные планы, лабораторные привязки, staff/teacher bindings).
- `import_dekanat_csv` — дозагрузка/обновление реальных людей и дисциплин из CSV (`students`, `teachers`, `staff`, `disciplines`, `groups`, `curriculum`, `lab_bindings`, `staff_bindings`).
- Если в CSV не передан `email`, команда автоматически генерирует служебный адрес вида `student-...@demo.local`.
- Django admin — только для точечной проверки и ручных правок в исключениях (не как основной канал наполнения).

Реализованные правила расписания и слотов:

- Запись доступна только в будние дни (Пн-Пт).
- Запись доступна только на университетские пары:
  - 1: `08:50-10:20`
  - 2: `10:35-12:05`
  - 3: `12:35-14:05`
  - 4: `14:15-15:45`
  - 5: `15:55-17:20`
  - 6: `17:30-19:00`
- При параллельных ЛР в одной аудитории учитывается суммарная загрузка аудитории по пересекающимся слотам.
- В UI записи студенту показываются только даты с реальными свободными местами и доступные пары для выбранной ЛР.

## Шаблоны CSV

Готовые шаблоны в `docs/csv_templates/`:

- `pilot_students.csv`
- `pilot_staff.csv`
- `pilot_teachers.csv`
- `pilot_disciplines.csv`
- `pilot_groups.csv` — учебные группы
- `pilot_curriculum.csv` — матрица группа → дисциплина (по коду)
- `pilot_lab_bindings.csv` — привязка дисциплин/ЛР к лаборатории
- `pilot_staff_bindings.csv` — привязка дисциплин к сотрудникам/преподавателям

## Команды наполнения

Локальный запуск:

```bash
cd backend
python manage.py migrate
python manage.py seed_demo --weeks 2
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_groups.csv --type=groups
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_disciplines.csv --type=disciplines --semester "Пилот 2026/2027 (нефтегаз)"
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_lab_bindings.csv --type=lab_bindings
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_curriculum.csv --type=curriculum
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_staff.csv --type=staff
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_teachers.csv --type=teachers
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_staff_bindings.csv --type=staff_bindings
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_students.csv --type=students
```

Через Docker на VM:

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py seed_demo --weeks 2
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /app/docs/csv_templates/pilot_groups.csv --type=groups
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /app/docs/csv_templates/pilot_disciplines.csv --type=disciplines --semester "Пилот 2026/2027 (нефтегаз)"
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /app/docs/csv_templates/pilot_lab_bindings.csv --type=lab_bindings
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /app/docs/csv_templates/pilot_curriculum.csv --type=curriculum
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /app/docs/csv_templates/pilot_staff.csv --type=staff
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /app/docs/csv_templates/pilot_teachers.csv --type=teachers
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /app/docs/csv_templates/pilot_staff_bindings.csv --type=staff_bindings
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /app/docs/csv_templates/pilot_students.csv --type=students
```

## Приёмочные тесты видимости

После `seed_demo` можно прогнать:

```bash
cd backend
pytest apps/bookings/tests/test_pilot_visibility.py -v
```

Тесты проверяют:

- студент `ТНГ-24` видит только дисциплины своей кафедры;
- студент `ЭХТ-24` и `НГС-18-2` не видят чужие учебные планы;
- сотрудник лаборатории видит все 31 дисциплину своей лаборатории;
- завлаб (`LAB_HEAD`) имеет доступ к кабинету завлаба и видимости лаборатории.

## Тестовые учётные записи после seed

- `zavlab.pilot@spmi.ru / pilot123` (завлаб, `LAB_HEAD`)
- `operator1.pilot@spmi.ru / pilot123`
- `operator2.pilot@spmi.ru / pilot123`
- `teacher.tng@spmi.ru / pilot123`
- `teacher.bur@spmi.ru / pilot123`
- `teacher.razr@spmi.ru / pilot123`
- `teacher.gas@spmi.ru / pilot123`
- `student001..student090@stud.local / student123`

Примеры для проверки учебных планов:

- `student001@stud.local` — группа `ТНГ-24`
- `student048@stud.local` — группа `ЭХТ-24`
- `student069@stud.local` — группа `НГС-18-2`
