#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGET_VERSION="${MAX_DEEPSEEK_TARGET_VERSION:-latest}"
BACKUP_DIR="${MAX_DEEPSEEK_BACKUP_DIR:-$ROOT_DIR/backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_PATH="$BACKUP_DIR/max-deepseek-$STAMP.tgz"

if [ -d docker/data ]; then
  tar -czf "$BACKUP_PATH" -C docker data
  echo "Backup: $BACKUP_PATH"
else
  echo "Skip backup: docker/data not found"
fi

if command -v docker >/dev/null 2>&1 && [ -f docker/docker-compose.yml ]; then
  if [ "$TARGET_VERSION" != "latest" ]; then
    export MAX_DEEPSEEK_VERSION="$TARGET_VERSION"
  fi
  docker compose -f docker/docker-compose.yml build
  docker compose -f docker/docker-compose.yml up -d
  echo "Docker update complete"
else
  echo "Docker compose not available. Please pull new source and restart service manually."
fi
