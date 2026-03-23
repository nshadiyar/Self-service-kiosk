#!/bin/sh
set -e

# PORT задаётся Railway; локально используется 8000
PORT="${PORT:-8000}"

# Миграции — асинхронно в фоне (lifespan.py). Startup не блокируется
echo "Starting FastAPI on 0.0.0.0:${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
