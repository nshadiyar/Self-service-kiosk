#!/bin/sh
set -e

# Railway задаёт PORT, локально fallback 8000
PORT="${PORT:-8000}"
export PORT

echo "=== STARTUP INFO ==="
echo "PORT: ${PORT}"
echo "HOST: 0.0.0.0"
echo "===================="

# Проверка доступности порта (nc может отсутствовать в slim-образе)
if command -v nc > /dev/null 2>&1; then
    if nc -z 0.0.0.0 "$PORT" 2>/dev/null; then
        echo "WARNING: Port ${PORT} is already in use"
    fi
fi

# Запуск uvicorn с явными параметрами для Railway proxy
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info \
    --access-log \
    --no-use-colors \
    --proxy-headers \
    --forwarded-allow-ips='*'
