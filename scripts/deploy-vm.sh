#!/usr/bin/env bash
# Деплой labbooking на VM (Ubuntu + Docker).
#
# Обычный деплой (код + миграции, БД не трогаем):
#   bash scripts/deploy-vm.sh
#
# Полный деплой с Excel (дисциплины, ЛР, студенты из data/import/xls/):
#   bash scripts/deploy-vm.sh --import-data
#
# Только догенерировать слоты:
#   bash scripts/deploy-vm.sh --generate-sessions

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMPORT_DATA=0
GENERATE_SESSIONS=0

for arg in "$@"; do
  case "$arg" in
    --import-data) IMPORT_DATA=1 ;;
    --generate-sessions) GENERATE_SESSIONS=1 ;;
    -h|--help)
      cat <<'EOF'
Использование: bash scripts/deploy-vm.sh [опции]

  (без опций)           Обновить код и миграции. Данные в БД не меняются.
  --import-data         seed_demo (завлаб/сотрудники) + Excel + generate_sessions
  --generate-sessions   Только generate_sessions --weeks 2
  -h, --help            Эта справка

Excel-файлы: data/import/xls/ЛР_учет*.xlsx
Завлаб/сотрудники: zavlab.pilot@spmi.ru, operator1.pilot@spmi.ru / pilot123
Студенты после импорта: s<номер_зачётки>@stud.spmi.ru / student123
EOF
      exit 0
      ;;
    *)
      echo "Неизвестный аргумент: $arg (см. --help)"
      exit 1
      ;;
  esac
done

if [[ ! -f .env ]]; then
  echo "Файл .env не найден. Скопируйте шаблон:"
  echo "  cp .env.vm.example .env"
  echo "  nano .env   # укажите ALLOWED_HOSTS и пароли"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не установлен. См. docs/DEPLOY_YANDEX_VM.md"
  exit 1
fi

USE_HTTPS=0
if [[ -f nginx/ssl/fullchain.pem && -f nginx/ssl/privkey.pem ]]; then
  USE_HTTPS=1
fi
if grep -qE '^USE_HTTPS=1' .env 2>/dev/null; then
  USE_HTTPS=1
fi

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.vm.yml"
if [[ "$USE_HTTPS" -eq 1 ]]; then
  if [[ ! -f nginx/ssl/fullchain.pem || ! -f nginx/ssl/privkey.pem ]]; then
    echo "USE_HTTPS=1, но нет nginx/ssl/fullchain.pem и privkey.pem."
    echo "Выполните: bash scripts/setup-https-ycm.sh <domain> ...  или  sudo bash scripts/setup-https.sh <domain>"
    exit 1
  fi
  COMPOSE="$COMPOSE -f docker-compose.https.yml"
  echo "==> Режим HTTPS (порты 80+443, nginx/ssl найден)"
else
  echo "==> Режим HTTP (только порт 80). После setup-https добавьте USE_HTTPS=1 в .env"
fi

echo "==> Сборка и запуск контейнеров..."
$COMPOSE up -d --build

echo "==> Ожидание готовности БД..."
for _ in $(seq 1 30); do
  if $COMPOSE exec -T db pg_isready -U "${POSTGRES_USER:-labbooking}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "==> Миграции..."
if ! $COMPOSE run --rm --no-deps web python manage.py migrate --noinput; then
  echo ""
  echo "ERROR: миграции не прошли. Последние логи web:"
  $COMPOSE logs web --tail 80 || true
  exit 1
fi

echo "==> Перезапуск web после миграций..."
$COMPOSE up -d web
sleep 3

XLS_DIR="data/import/xls"
if [[ "$IMPORT_DATA" -eq 1 ]]; then
  echo "==> Завлаб и сотрудники (seed_demo)..."
  $COMPOSE exec -T web python manage.py seed_demo

  shopt -s nullglob
  xlsx_files=("${XLS_DIR}"/ЛР_учет*.xlsx)
  shopt -u nullglob
  if [[ ${#xlsx_files[@]} -eq 0 ]]; then
    echo "ERROR: --import-data указан, но в ${XLS_DIR}/ нет файлов ЛР_учет*.xlsx"
    exit 1
  fi
  echo "==> Импорт данных из ${XLS_DIR} (${#xlsx_files[@]} файлов)..."
  $COMPOSE exec -T web mkdir -p /tmp/labs
  $COMPOSE cp "${XLS_DIR}/." web:/tmp/labs/
  $COMPOSE exec -T web python manage.py import_lr_accounting_xlsx /tmp/labs --clear-existing
  GENERATE_SESSIONS=1
fi

if [[ "$GENERATE_SESSIONS" -eq 1 ]]; then
  echo "==> Генерация слотов (может занять несколько минут)..."
  $COMPOSE exec -T web python manage.py generate_sessions --weeks 2
fi

echo "==> Статика..."
$COMPOSE exec -T web python manage.py collectstatic --noinput

if $COMPOSE exec -T web test -f /app/staticfiles/img/spmi-logo.png; then
  echo "==> Логотип: staticfiles/img/spmi-logo.png найден"
else
  echo "WARN: логотип не найден в staticfiles. Проверьте backend/static/img/spmi-logo.png"
fi

if $COMPOSE exec -T web test -f /app/staticfiles/img/spmi-logo.svg; then
  echo "==> Favicon SVG: staticfiles/img/spmi-logo.svg найден"
else
  echo "WARN: spmi-logo.svg не найден в staticfiles. Проверьте backend/static/img/spmi-logo.svg"
fi

SMOKE_URL="http://127.0.0.1"
if [[ "$USE_HTTPS" -eq 1 ]]; then
  SMOKE_URL=$(grep -E '^SITE_URL=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "'\''' || true)
  if [[ -z "$SMOKE_URL" ]]; then
    FIRST_HOST=$(grep -E '^ALLOWED_HOSTS=' .env | cut -d= -f2- | cut -d, -f1 | tr -d ' ')
    if [[ -n "$FIRST_HOST" && "$FIRST_HOST" != "localhost" && "$FIRST_HOST" != "127.0.0.1" ]]; then
      SMOKE_URL="https://$FIRST_HOST"
    else
      SMOKE_URL="https://127.0.0.1"
    fi
  fi
  SMOKE_URL="${SMOKE_URL%/}"
fi

echo ""
echo "==> Smoke test ($SMOKE_URL)..."
if bash scripts/smoke-test.sh "$SMOKE_URL"; then
  echo ""
  echo "Деплой успешен."
else
  echo "Smoke test не прошёл — проверьте логи: $COMPOSE logs web nginx"
fi
echo ""
if [[ "$USE_HTTPS" -eq 1 ]]; then
  echo "Сайт: $SMOKE_URL/"
  echo "Swagger: $SMOKE_URL/api/docs/"
else
  echo "Сайт: http://<PUBLIC_IP>/"
  echo "Swagger: http://<PUBLIC_IP>/api/docs/"
  echo "HTTPS: bash scripts/setup-https-ycm.sh <DOMAIN> ...  затем USE_HTTPS=1 в .env"
fi
echo "Студенты: s<номер_зачётки>@stud.spmi.ru / student123"
echo "Завлаб/сотрудники: zavlab.pilot@spmi.ru, operator1.pilot@spmi.ru / pilot123"
echo "Импорт Excel: bash scripts/deploy-vm.sh --import-data"
echo "Слияние каталога (studlab + workload drafts): bash scripts/sync-catalog-vm.sh --generate-sessions"
