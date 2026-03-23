#!/bin/sh
set -e

# Миграции выполняются асинхронно в фоне при старте приложения (lifespan.py)
# Не блокируем startup — приложение сразу готово к приёму запросов
echo "Starting FastAPI on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
