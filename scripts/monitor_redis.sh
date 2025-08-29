#!/usr/bin/env bash
set -euo pipefail

HOST="${REDIS_HOST:-127.0.0.1}"
PORT="${REDIS_PORT:-6379}"

echo "Attempting to monitor Redis at $HOST:$PORT ..."
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' | grep -q '^redis$'; then
    echo "Using Docker container 'redis' ..."
    exec docker exec -it redis redis-cli monitor
  fi
fi

if command -v redis-cli >/dev/null 2>&1; then
  exec redis-cli -h "$HOST" -p "$PORT" monitor
else
  echo "redis-cli not found. Install Redis tools or run via Docker container named 'redis'."
  exit 1
fi
