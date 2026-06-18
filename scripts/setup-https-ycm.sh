#!/usr/bin/env bash
# HTTPS с сертификатом из Yandex Certificate Manager (статус Issued).
# Запуск на VM:
#   bash scripts/setup-https-ycm.sh spmi-lab.ru <CERTIFICATE_ID>
# или по имени:
#   bash scripts/setup-https-ycm.sh spmi-lab.ru --name cert-spmi-lab
#
# Нужны: yc CLI (авторизован), порт 443 в Security Group, A-запись домена → IP VM.

set -euo pipefail

DOMAIN="${1:-}"
CERT_REF="${2:-}"

if [[ -z "$DOMAIN" || -z "$CERT_REF" ]]; then
  echo "Использование:"
  echo "  bash scripts/setup-https-ycm.sh <domain> <certificate_id>"
  echo "  bash scripts/setup-https-ycm.sh <domain> --name <certificate_name>"
  exit 1
fi

if ! command -v yc >/dev/null 2>&1; then
  echo "Установите Yandex Cloud CLI: https://yandex.cloud/ru/docs/cli/quickstart"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NGINX_SSL="$ROOT/nginx/ssl"
mkdir -p "$NGINX_SSL"
chmod 700 "$NGINX_SSL"

YC_ARGS=()
if [[ "$CERT_REF" == "--name" ]]; then
  YC_ARGS+=(--name "${3:-}")
  if [[ -z "${3:-}" ]]; then
    echo "Укажите имя сертификата после --name"
    exit 1
  fi
else
  YC_ARGS+=(--id "$CERT_REF")
fi

echo "==> Скачивание сертификата из Certificate Manager..."
yc certificate-manager certificate content get \
  "${YC_ARGS[@]}" \
  --chain "$NGINX_SSL/fullchain.pem" \
  --key "$NGINX_SSL/privkey.pem"

chmod 600 "$NGINX_SSL/privkey.pem"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.vm.yml -f docker-compose.https.yml"

echo "==> Запуск nginx с HTTPS..."
$COMPOSE up -d --build

echo ""
echo "Готово. Проверьте в .env:"
echo "  ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN,<PUBLIC_IP>,localhost,127.0.0.1"
echo "  CSRF_TRUSTED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN"
echo "  SECURE_SSL_REDIRECT=1"
echo ""
echo "Затем: $COMPOSE up -d web"
echo "Сайт: https://$DOMAIN/"
