#!/bin/sh
set -e

# PORT задаётся Railway; локально fallback 8000
PORT="${PORT:-8000}"
export PORT

echo "PORT=${PORT} — starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
