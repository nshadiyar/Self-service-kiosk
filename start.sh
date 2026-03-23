#!/bin/sh
set -e

# PORT задаётся Railway; локально fallback 8000
PORT="${PORT:-8000}"
export PORT

echo "Starting FastAPI on 0.0.0.0:${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
