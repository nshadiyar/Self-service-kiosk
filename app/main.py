"""
FastAPI application — быстрый startup для Railway (устраняет 502).

- / и /health — мгновенный ответ, без БД
- /health/db — проверка БД через AsyncSessionLocal с таймаутом 3 сек
- DATABASE_URL: postgres:// → postgresql://, +asyncpg для asyncpg (app.config)
"""
import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.core.logging_config import setup_logging
from app.core.lifespan import lifespan
from app.core.middleware import register_middleware
from app.core.exception_handlers import register_exception_handlers
from app.api.v1.router import router as api_v1_router

setup_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Self-service kiosk ordering system for inmates in Kazakhstan prisons",
    lifespan=lifespan,
)

register_middleware(app)
register_exception_handlers(app)
app.include_router(api_v1_router)


@app.get("/")
async def root():
    """Мгновенный ответ без БД."""
    return JSONResponse({"status": "ok", "version": settings.app_version})


@app.get("/health")
async def health_check():
    """Мгновенный ответ без БД."""
    return JSONResponse({"status": "ok", "version": settings.app_version})


@app.get("/health/db")
async def health_db():
    """
    Проверка БД через AsyncSessionLocal с таймаутом 3 сек.
    """
    from app.database import AsyncSessionLocal
    from app.core.lifespan import scheduler

    status = "ok"
    try:
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=3)
    except Exception as e:
        status = f"error: {e}"

    return JSONResponse(
        {
            "status": "ok" if status == "ok" else "degraded",
            "version": settings.app_version,
            "database": status,
            "scheduler": "running" if scheduler and scheduler.running else "stopped",
        }
    )
