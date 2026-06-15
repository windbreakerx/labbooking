#!/usr/bin/env bash
set -euo pipefail
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-labbooking}" "${POSTGRES_DB:-labbooking}" > "backup_$(date +%Y%m%d_%H%M%S).sql"
