#!/usr/bin/env bash
# Деплой labbooking на VM (Ubuntu + Docker).
# Запуск на сервере из корня репозитория: bash scripts/deploy-vm.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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

echo "==> Ожидание готовности web..."
sleep 5

echo "==> Демо-данные (если БД пустая — безопасно повторять)..."
$COMPOSE exec -T web python manage.py seed_demo --weeks 2 || true

echo "==> Миграции..."
$COMPOSE exec -T web python manage.py migrate --noinput

echo "==> Статика..."
$COMPOSE exec -T web python manage.py collectstatic --noinput

if $COMPOSE exec -T web test -f /app/staticfiles/img/spmi-logo.png; then
  echo "==> Логотип: staticfiles/img/spmi-logo.png найден"
else
  echo "WARN: логотип не найден в staticfiles. Проверьте backend/static/img/spmi-logo.png"
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
echo "Демо: student@stud.spmi.ru / student123"
