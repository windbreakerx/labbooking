#!/usr/bin/env bash
# Прогон pytest на VM внутри контейнера web.
# Запуск из корня репозитория: bash scripts/run-tests-vm.sh
#
# Примеры:
#   bash scripts/run-tests-vm.sh              # все тесты в apps/
#   bash scripts/run-tests-vm.sh --pilot      # быстрый pilot-набор (~141)
#   bash scripts/run-tests-vm.sh apps/bookings/tests/test_staff_scope.py -v
#   bash scripts/run-tests-vm.sh --full       # то же, что без аргументов (совместимость)

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
  # Контейнер web задаёт DJANGO_SETTINGS_MODULE=prod — pytest-django берёт его из env,
  # из-за SECURE_SSL_REDIRECT тесты получают 301. Принудительно включаем test settings.
  # PYTEST_CACHE_DIR — appuser не может писать в /app/.pytest_cache в production-образе.
  $COMPOSE exec -T web sh -c 'export PYTEST_CACHE_DIR=/tmp/pytest-cache; DJANGO_SETTINGS_MODULE=config.settings.test python -m pytest "$@"' sh "$@"
}

install_dev_deps

if [[ "${1:-}" == "--pilot" ]]; then
  shift
  run_pytest -v "${PILOT_TESTS[@]}" "$@"
elif [[ "${1:-}" == "--full" ]]; then
  shift
  run_pytest -v apps/ "$@"
elif [[ $# -gt 0 ]]; then
  run_pytest "$@"
else
  run_pytest -v apps/
fi
