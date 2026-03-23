#!/bin/sh
set -e

echo "🚀 Starting Bromart Kiosk API..."
echo "📊 Running database migrations..."

# Run migrations with timeout
timeout 60 alembic upgrade head || {
    echo "❌ Migration timeout or failed"
    exit 1
}

echo "✅ Migrations completed"
echo "🌐 Starting FastAPI server on port ${PORT:-8000}..."

# Start FastAPI with production settings
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --log-level info \
    --no-access-log \
    --loop uvloop \
    --http httptools \
    --workers 1 \
    --timeout-keep-alive 5 \
    --timeout-graceful-shutdown 10
