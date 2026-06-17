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

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.vm.yml"

echo "==> Сборка и запуск контейнеров..."
$COMPOSE up -d --build

echo "==> Ожидание готовности web..."
sleep 5

echo "==> Демо-данные (если БД пустая — безопасно повторять)..."
$COMPOSE exec -T web python manage.py seed_demo || true

echo "==> Миграции..."
$COMPOSE exec -T web python manage.py migrate --noinput

echo "==> Статика..."
$COMPOSE exec -T web python manage.py collectstatic --noinput

echo ""
echo "==> Smoke test..."
if bash scripts/smoke-test.sh http://127.0.0.1; then
  echo ""
  echo "Деплой успешен."
else
  echo "Smoke test не прошёл — проверьте логи: $COMPOSE logs web"
fi
echo ""
echo "Сайт: http://<PUBLIC_IP>/ или https://<DOMAIN>/"
echo "Swagger: http://<PUBLIC_IP>/api/docs/"
echo "HTTPS: sudo bash scripts/setup-https.sh <DOMAIN>"
echo "Демо: student@stud.spmi.ru / student123"
