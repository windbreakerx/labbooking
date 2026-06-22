#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.vm.yml}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
POSTGRES_USER="${POSTGRES_USER:-labbooking}"
POSTGRES_DB="${POSTGRES_DB:-labbooking}"

mkdir -p "$BACKUP_DIR"
backup_path="$BACKUP_DIR/labbooking_${POSTGRES_DB}_$(date +%Y%m%d_%H%M%S).sql"

# shellcheck disable=SC2086
docker compose $COMPOSE_FILES exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$backup_path"
echo "Backup saved to $backup_path"
