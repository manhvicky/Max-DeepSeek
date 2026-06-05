#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DIR="${MAX_DEEPSEEK_BACKUP_DIR:-$ROOT_DIR/backups}"
LATEST_BACKUP="$(ls -1t "$BACKUP_DIR"/max-deepseek-*.tgz 2>/dev/null | head -n 1 || true)"

if [ -z "$LATEST_BACKUP" ]; then
  echo "Khong tim thay backup de rollback"
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

tar -xzf "$LATEST_BACKUP" -C "$TMP_DIR"
rm -rf docker/data
mv "$TMP_DIR"/data docker/data

echo "Da phuc hoi du lieu tu $LATEST_BACKUP"
if command -v docker >/dev/null 2>&1 && [ -f docker/docker-compose.yml ]; then
  docker compose -f docker/docker-compose.yml up -d
  echo "Docker rollback complete"
else
  echo "Hay khoi dong lai dich vu thu cong."
fi
