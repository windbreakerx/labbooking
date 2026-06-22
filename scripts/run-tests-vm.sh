#!/usr/bin/env bash
# Прогон pytest на VM внутри контейнера web.
# Запуск из корня репозитория: bash scripts/run-tests-vm.sh
#
# Примеры:
#   bash scripts/run-tests-vm.sh
#   bash scripts/run-tests-vm.sh apps/bookings/tests/test_staff_scope.py -v
#   bash scripts/run-tests-vm.sh --full

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PILOT_TESTS=(
  apps/bookings/tests/test_booking.py
  apps/bookings/tests/test_student_scope.py
  apps/bookings/tests/test_staff_scope.py
  apps/bookings/tests/test_manual_booking.py
  apps/bookings/tests/test_lab_head_ui.py
  apps/bookings/tests/test_pilot_visibility.py
)

if [[ ! -f .env ]]; then
  echo "Файл .env не найден. Сначала настройте VM: cp .env.vm.example .env"
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
  COMPOSE="$COMPOSE -f docker-compose.https.yml"
fi

if ! $COMPOSE exec -T web true 2>/dev/null; then
  echo "Контейнер web не запущен. Сначала выполните:"
  echo "  bash scripts/deploy-vm.sh"
  exit 1
fi

install_dev_deps() {
  echo "==> Установка dev-зависимостей (pytest) в контейнер web..."
  # От root — иначе pip install под appuser кладёт бинарники в ~/.local/bin вне PATH.
  $COMPOSE exec -T -u root web python -m pip install --no-cache-dir -r requirements-dev.txt
  echo "==> Проверка pytest..."
  $COMPOSE exec -T web python -m pytest --version
}

run_pytest() {
  echo "==> Запуск: python -m pytest $*"
  # python -m pytest надёжнее, чем bare pytest, если бинарник не в PATH.
  $COMPOSE exec -T web python -m pytest "$@"
}

install_dev_deps

if [[ "${1:-}" == "--full" ]]; then
  shift
  run_pytest "$@"
elif [[ $# -gt 0 ]]; then
  run_pytest "$@"
else
  run_pytest -v "${PILOT_TESTS[@]}"
fi
