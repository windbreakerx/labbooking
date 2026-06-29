#!/usr/bin/env bash
# Vendors HTMX for self-hosted static (fallback CDN in base.html if missing).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/backend/static/js/htmx.min.js"
URL="https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$OUT"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "$OUT" "$URL"
else
  echo "Install curl or wget to fetch HTMX." >&2
  exit 1
fi

echo "Saved $(wc -c < "$OUT") bytes to $OUT"
