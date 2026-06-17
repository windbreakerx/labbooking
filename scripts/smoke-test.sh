#!/usr/bin/env bash
# Smoke-тест после деплоя labbooking.
# Использование: bash scripts/smoke-test.sh [BASE_URL]
# По умолчанию: http://127.0.0.1

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1}"
FAILED=0

check() {
  local name="$1"
  local url="$2"
  local expected="${3:-200}"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
  if [[ "$code" == "$expected" ]]; then
    echo "OK  $name ($code)"
  else
    echo "FAIL $name (expected $expected, got $code) — $url"
    FAILED=1
  fi
}

echo "==> Smoke test: $BASE_URL"
check "health" "$BASE_URL/api/health/"
check "home redirect/login" "$BASE_URL/" "302"
check "login page" "$BASE_URL/login/" "200"
check "swagger" "$BASE_URL/api/docs/" "200"

if [[ $FAILED -eq 0 ]]; then
  echo ""
  echo "Все проверки пройдены."
  exit 0
else
  echo ""
  echo "Есть ошибки. Проверьте логи: docker compose logs web"
  exit 1
fi
