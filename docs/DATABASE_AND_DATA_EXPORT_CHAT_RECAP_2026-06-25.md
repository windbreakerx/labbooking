# База данных и экспорт данных — Recap чата (2026-06-25)

## Вопрос

Как сейчас создаётся база данных? БД создаётся внутри контейнера, но по мере работы сайта будет заполняться сотрудниками. Как извлечь эти данные / БД для дальнейшего использования? Пока нет нормальной базы, связанной с лабораторными работами.

---

## Краткий ответ

Понимание в целом верное, но с важными нюансами:

- PostgreSQL работает в Docker-контейнере, но данные **сохраняются в именованном томе** `postgres_data` и не теряются при перезапуске контейнера.
- Схема таблиц создаётся Django-миграциями (`manage.py migrate`) при старте `web`.
- Наполнение БД — **не только** ручной работой сотрудников: есть `seed_demo`, импорт из Excel `ЛР_учет*.xlsx`, CSV-импорт и UI завлаба/staff.
- Полный дамп уже поддерживается скриптом `scripts/backup_db.sh`.
- Отдельной внешней «базы лабораторных работ» (как у lr.spmi.ru или Деканата) пока нет — каталог ЛР живёт в PostgreSQL и пополняется импортом и UI.

---

## Как создаётся БД

### Инфраструктура

В `docker-compose.yml` поднимается сервис `db` (PostgreSQL 16):

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-labbooking}
      POSTGRES_USER: ${POSTGRES_USER:-labbooking}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-labbooking}
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

Данные лежат в Docker-томе `postgres_data`, а не «эфемерно внутри контейнера».

### Схема таблиц

При старте контейнера `web` выполняется:

```bash
python manage.py migrate --noinput
```

Django создаёт и обновляет таблицы по миграциям. Это происходит и локально, и на VM при каждом деплое.

### Подключение

- **В Docker / на VM:** `DATABASE_URL` → PostgreSQL (`postgres://...@db:5432/labbooking`).
- **Локально без Docker:** fallback на SQLite (`backend/db.sqlite3`), если `DATABASE_URL` не задан.

Настройка в `backend/config/settings/base.py`:

```python
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
```

---

## Откуда берутся данные

Сейчас это не только ручной ввод сотрудниками. Есть несколько каналов:

| Канал | Что загружает |
|-------|----------------|
| `seed_demo` | Пилотный набор: семестр, 31 дисциплина, ~36 ЛР, группы, студенты, слоты |
| `import_lr_accounting_xlsx` | Реальные журналы `ЛР_учет*.xlsx` — дисциплины, ЛР, группы, студенты |
| `import_dekanat_csv` | CSV-шаблоны (группы, дисциплины, привязки, люди) |
| UI завлаба / staff | Создание дисциплин, ЛР, расписания, привязок |
| Работа сайта | Записи студентов (`Booking`), статусы, тикеты поддержки |

### Команды наполнения

Локально:

```bash
cd backend
python manage.py migrate
python manage.py seed_demo --weeks 2
```

Полный импорт из Excel на VM:

```bash
bash scripts/deploy-vm.sh --import-data
```

Файлы ожидаются в `data/import/xls/ЛР_учет*.xlsx`.

По документации пилота (`docs/PILOT_DATA_SETUP.md`) основной путь — **seed_demo + CSV**, а UI — для доработок в процессе работы, не как единственный источник каталога ЛР.

### Ключевые модели академического слоя

- `Semester` — семестр
- `Discipline` — дисциплина
- `LabWork` — лабораторная работа
- `StudentGroup` — учебная группа (с привязками к дисциплинам и ЛР)
- `TrainingCenter`, `Room`, `LabSession` — расписание и аудитории
- `Booking` — записи студентов

---

## Как извлечь данные

### 1. Полный дамп PostgreSQL (рекомендуется)

Скрипт `scripts/backup_db.sh`:

```bash
bash scripts/backup_db.sh
```

Сохраняет SQL-файл в `backups/labbooking_labbooking_YYYYMMDD_HHMMSS.sql` через `pg_dump`. Это полная копия всего: дисциплины, ЛР, группы, пользователи, записи, расписание.

Восстановление на другой машине (`docs/DEPLOY_YANDEX_VM.md`):

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T db createdb -U labbooking labbooking_restore_check
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T db psql -U labbooking -d labbooking_restore_check < backups/<backup-file>.sql
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T db dropdb -U labbooking labbooking_restore_check
```

Каталог `backups/` в `.gitignore` — не коммитить дампы с персональными данными.

### 2. Выборочный экспорт через команды и UI

| Способ | Что даёт |
|--------|----------|
| `python manage.py export_students_csv output.csv` | Логины и группы студентов |
| Раздел «Отчёты» в staff UI | Excel: записи, посещаемость, сводка по дисциплинам |
| API `GET /api/v1/admin/reports/{type}/` | Те же отчёты через API (для staff) |

### 3. Django `dumpdata` (вручную)

Готовой команды нет, но можно выгрузить отдельные приложения:

```bash
docker compose exec web python manage.py dumpdata academics --indent 2 -o academics.json
docker compose exec web python manage.py dumpdata scheduling --indent 2 -o scheduling.json
```

### 4. Исходные Excel-журналы

Каталог ЛР изначально задуман как импорт из `ЛР_учет*.xlsx`. Если файлы есть в `data/import/xls/`, они — исходный «эталон» по лабораторным работам; PostgreSQL — рабочая копия после импорта и правок в UI.

Парсер: `backend/apps/integrations/lr_accounting/parser.py`  
Команда импорта: `backend/apps/academics/management/commands/import_lr_accounting_xlsx.py`

---

## Про «нет нормальной базы ЛР»

В проекте **есть** модели `Discipline`, `LabWork`, `StudentGroup` и связи между ними в PostgreSQL. Отдельной внешней справочной БД лабораторных работ (как у lr.spmi.ru или Деканата) пока нет — это осознанный выбор пилота:

- **Сейчас:** Excel `ЛР_учет` → импорт → Postgres; доработки через кабинет завлаба.
- **После пилота:** интеграция с API Деканата, CSV остаётся запасным путём (`docs/POST_PILOT_ROADMAP.md`).

Данные, которые сотрудники вводят через сайт, уже в Postgres — их можно снять дампом.

---

## Практические рекомендации

### Сохранить всё, что накопится за время пилота

```bash
# на VM, перед обновлениями и периодически
bash scripts/backup_db.sh
```

Скопировать файл из `backups/` на локальную машину (`scp` / `rsync`). Это даст полную БД для анализа, миграции или подключения к другому окружению.

### Если нужен справочник ЛР без персональных данных

Варианты:

1. Регулярно делать `backup_db.sh` (операционные данные + каталог).
2. Периодически выгружать академический слой (`dumpdata academics scheduling` или SQL к таблицам `academics_*`).
3. Для полного каталога — догрузить все `ЛР_учет*.xlsx` через `deploy-vm.sh --import-data`, либо накопить правки из UI и экспортировать.

Возможное улучшение (обсуждалось, не реализовано): команда `export_lab_catalog_csv` — дисциплины + ЛР + привязки к группам/аудиториям.

---

## Связанные файлы и документы

| Путь | Назначение |
|------|------------|
| `docker-compose.yml` | Postgres, Redis, web, nginx |
| `docker-compose.vm.yml` | Overlay для VM (без публикации портов БД) |
| `scripts/backup_db.sh` | Дамп PostgreSQL |
| `scripts/deploy-vm.sh` | Деплой; `--import-data` для Excel |
| `backend/apps/academics/models.py` | Semester, Discipline, LabWork, StudentGroup |
| `docs/PILOT_DATA_SETUP.md` | Сценарий наполнения пилотных данных |
| `docs/DEPLOY_YANDEX_VM.md` | Backup/restore на VM |
| `docs/POST_PILOT_ROADMAP.md` | Интеграции после пилота |
