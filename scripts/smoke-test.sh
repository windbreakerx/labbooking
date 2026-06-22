#!/usr/bin/env bash
# Smoke-тест после деплоя labbooking.
# Использование: bash scripts/smoke-test.sh [BASE_URL]
# По умолчанию: http://127.0.0.1, или SITE_URL из .env при USE_HTTPS=1

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

resolve_default_base_url() {
  local url="http://127.0.0.1"
  if [[ -f "$ROOT/.env" ]] && grep -qE '^USE_HTTPS=1' "$ROOT/.env" 2>/dev/null; then
    url=$(grep -E '^SITE_URL=' "$ROOT/.env" 2>/dev/null | cut -d= -f2- | tr -d ' "'\''' || true)
    if [[ -z "$url" ]]; then
      local host
      host=$(grep -E '^ALLOWED_HOSTS=' "$ROOT/.env" 2>/dev/null | cut -d= -f2- | cut -d, -f1 | tr -d ' ')
      if [[ -n "$host" && "$host" != "localhost" && "$host" != "127.0.0.1" ]]; then
        url="https://$host"
      else
        url="https://127.0.0.1"
      fi
    fi
  fi
  echo "${url%/}"
}

BASE_URL="${1:-$(resolve_default_base_url)}"
FAILED=0

check() {
  local name="$1"
  local url="$2"
  local expected="${3:-200}"
  local code
  local curl_opts=(-s -o /dev/null -w "%{http_code}")
  if [[ "$url" == https://* ]]; then
    curl_opts=(-k "${curl_opts[@]}")
  fi
  code=$(curl "${curl_opts[@]}" "$url" || echo "000")
  if [[ "$code" == "$expected" ]]; then
    echo "OK  $name ($code)"
  else
    echo "FAIL $name (expected $expected, got $code) — $url"
    FAILED=1
  fi
}

check_redirect() {
  local name="$1"
  local url="$2"
  shift 2
  local expected code
  local curl_opts=(-s -o /dev/null -w "%{http_code}")
  if [[ "$url" == https://* ]]; then
    curl_opts=(-k "${curl_opts[@]}")
  fi
  code=$(curl "${curl_opts[@]}" "$url" || echo "000")
  for expected in "$@"; do
    if [[ "$code" == "$expected" ]]; then
      echo "OK  $name ($code)"
      return
    fi
  done
  echo "FAIL $name (expected one of: $*, got $code) — $url"
  FAILED=1
}

echo "==> Smoke test: $BASE_URL"
check "health" "$BASE_URL/api/health/"
check_redirect "home redirect/login" "$BASE_URL/" 302 301
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
