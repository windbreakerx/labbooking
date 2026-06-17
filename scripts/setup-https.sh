#!/usr/bin/env bash
# Настройка HTTPS (Let's Encrypt) для labbooking на VM.
# Запуск: sudo bash scripts/setup-https.sh your.domain.ru
# Требования: домен указывает на IP VM, порт 80 открыт.

set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "Использование: sudo bash scripts/setup-https.sh your.domain.ru"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v certbot >/dev/null 2>&1; then
  apt-get update
  apt-get install -y certbot
fi

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.vm.yml"

echo "==> Остановка nginx для standalone certbot..."
$COMPOSE stop nginx || true

certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" || {
  echo "Certbot failed. Запустите nginx снова: $COMPOSE up -d nginx"
  exit 1
}

CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
NGINX_SSL="$ROOT/nginx/ssl"
mkdir -p "$NGINX_SSL"
cp "$CERT_DIR/fullchain.pem" "$NGINX_SSL/fullchain.pem"
cp "$CERT_DIR/privkey.pem" "$NGINX_SSL/privkey.pem"

if ! grep -q "$DOMAIN" .env 2>/dev/null; then
  echo ""
  echo "Добавьте в .env:"
  echo "  ALLOWED_HOSTS=$DOMAIN,<PUBLIC_IP>,localhost"
  echo "  CSRF_TRUSTED_ORIGINS=https://$DOMAIN"
  echo "  SECURE_SSL_REDIRECT=1"
fi

echo "==> Запуск с HTTPS overlay..."
$COMPOSE -f docker-compose.https.yml up -d --build

echo ""
echo "HTTPS: https://$DOMAIN/"
echo "Обновление сертификата (cron): certbot renew --pre-hook '$COMPOSE stop nginx' --post-hook 'cp $CERT_DIR/*.pem $NGINX_SSL/ && $COMPOSE -f docker-compose.https.yml up -d nginx'"
