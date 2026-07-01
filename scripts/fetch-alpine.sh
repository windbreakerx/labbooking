#!/usr/bin/env bash
# Vendors Alpine.js for self-hosted static delivery.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/backend/static/js/alpine.min.js"
URL="https://cdn.jsdelivr.net/npm/alpinejs@3.14.8/dist/cdn.min.js"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$OUT"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "$OUT" "$URL"
else
  echo "Install curl or wget to fetch Alpine.js." >&2
  exit 1
fi

echo "Saved $(wc -c < "$OUT") bytes to $OUT"
