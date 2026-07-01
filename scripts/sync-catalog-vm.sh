#!/usr/bin/env bash
# Слияние studlab + department catalog drafts с данными НГФ.
#
# Вызывается из deploy-vm.sh --import-data или вручную после git pull:
#   bash scripts/sync-catalog-vm.sh --generate-sessions
#
# Без --import-data не удаляет НГФ из ЛР_учет (только добавляет/обновляет).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GENERATE_SESSIONS=0
for arg in "$@"; do
  case "$arg" in
    --generate-sessions) GENERATE_SESSIONS=1 ;;
    -h|--help)
      cat <<'EOF'
Использование: bash scripts/sync-catalog-vm.sh [--generate-sessions]

  1. import_studlab_org     — факультеты, УЦ, лаборатории, аудитории, staff
  2. dedupe_lab_works       — объединить дубли ЛР (в т.ч. из ЛР_учет)
  3. import_curated_catalog — дисциплины/ЛР/учебные планы из *_draft
  4. dedupe_lab_works       — повторно после импорта
  5. generate_workload_students — студенты по численности групп (без НГФ-групп с аккаунтами)
  6. pilot_staff.csv        — реальные завлабы/сотрудники КУЛ НГФ
  7. generate_sessions      — только с --generate-sessions

Студенты НГФ из ЛР_учет не трогаются (skip_existing_groups).
EOF
      exit 0
      ;;
    *)
      echo "Неизвестный аргумент: $arg"
      exit 1
      ;;
  esac
done

if [[ ! -f .env ]]; then
  echo "Файл .env не найден."
  exit 1
fi

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.vm.yml"
if [[ -f nginx/ssl/fullchain.pem && -f nginx/ssl/privkey.pem ]] || grep -qE '^USE_HTTPS=1' .env 2>/dev/null; then
  COMPOSE="$COMPOSE -f docker-compose.https.yml"
fi

STUDLAB_DIR="docs/csv_templates/studlab_draft"
TEMPLATES_DIR="docs/csv_templates"
CONTAINER_TEMPLATES_DIR="/tmp/csv_templates"
CONTAINER_STUDLAB_DIR="/tmp/csv_templates/studlab_draft"
SEMESTER="Весна 2025/2026"

if [[ ! -d "$TEMPLATES_DIR/studlab_draft" ]]; then
  echo "ERROR: на хосте нет ${TEMPLATES_DIR}/studlab_draft (выполните git pull?)"
  exit 1
fi

echo "==> Копирование CSV-каталогов в контейнер..."
$COMPOSE exec -T web mkdir -p "$CONTAINER_TEMPLATES_DIR"
$COMPOSE cp "${TEMPLATES_DIR}/." "web:${CONTAINER_TEMPLATES_DIR}/"

run() {
  echo "==> $*"
  $COMPOSE exec -T web python manage.py "$@"
}

echo "==> Оргструктура studlab..."
run import_studlab_org "$CONTAINER_STUDLAB_DIR"

echo "==> Дедупликация ЛР (до импорта каталога)..."
run dedupe_lab_works

echo "==> Каталоги кафедр из workload drafts..."
run import_curated_catalog \
  --templates-dir "$CONTAINER_TEMPLATES_DIR" \
  --studlab-dir "$CONTAINER_STUDLAB_DIR" \
  --semester "$SEMESTER"

echo "==> Дедупликация ЛР (после импорта)..."
run dedupe_lab_works

echo "==> Студенты по численности групп (новые кафедры)..."
run generate_workload_students \
  --templates-dir "$CONTAINER_TEMPLATES_DIR" \
  --academic-year "2025-2026" \
  --students-per-group 5

if [[ -f "$TEMPLATES_DIR/pilot_staff.csv" ]]; then
  echo "==> Staff НГФ (pilot_staff.csv)..."
  run import_dekanat_csv "${CONTAINER_TEMPLATES_DIR}/pilot_staff.csv" --type staff --default-password pilot123
fi

if [[ "$GENERATE_SESSIONS" -eq 1 ]]; then
  echo "==> Генерация слотов..."
  run generate_sessions --weeks 2
fi

echo ""
echo "Синхронизация каталога завершена."
