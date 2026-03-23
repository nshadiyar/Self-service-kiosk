#!/bin/sh
set -e

echo "🚀 Starting Bromart Kiosk API..."
echo "📊 Running database migrations..."
alembic upgrade head

echo "🌐 Starting FastAPI server on port ${PORT:-8000}..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --log-level info \
    --no-access-log
