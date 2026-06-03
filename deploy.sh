#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/pc/apps/Max-DeepSeek"
CONTAINER="max-deepseek"
IMAGE="max-deepseek:latest"
PORT="22218"

cd "$APP_DIR"

echo "[1/5] Build frontend"
cd web
npm run build
cd "$APP_DIR"

echo "[2/5] Build Docker image"
docker build -t "$IMAGE" -f docker/Dockerfile .

echo "[3/5] Restart container"
if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
fi

docker run -d \
  --name "$CONTAINER" \
  --restart unless-stopped \
  -p "$PORT:$PORT" \
  -e DATA_DIR=/app/data \
  -e DS_MIN_ACCOUNT_INTERVAL_MS=45000 \
  -e DS_RESERVE_IDLE_MIN=0 \
  -v "$APP_DIR/docker/data:/app/data" \
  "$IMAGE" >/dev/null

echo "[4/5] Wait health"
for i in {1..30}; do
  if curl -fsS "http://localhost:$PORT/health" >/dev/null; then
    echo "Health OK"
    break
  fi
  sleep 1
  if [[ "$i" == "30" ]]; then
    echo "Health check failed" >&2
    docker logs "$CONTAINER" --tail 100 >&2 || true
    exit 1
  fi
done

echo "[5/5] Status"
docker ps --filter "name=$CONTAINER" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo "DONE"
