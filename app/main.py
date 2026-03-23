"""
FastAPI application — быстрый startup для Railway.

- / и /health отвечают мгновенно, без обращения к БД (устраняет 502)
- /health/db — проверка БД с таймаутом 3 сек
- DATABASE_URL читается из окружения (Railway), нормализуется для asyncpg в app.config
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

HEALTH_DB_TIMEOUT = 3.0


@app.get("/")
async def root():
    """
    Корневой endpoint — мгновенный ответ без обращения к БД.
    Railway health probe использует этот или /health для проверки доступности.
    """
    return JSONResponse({"status": "ok", "version": settings.app_version})


@app.get("/health")
async def health_check():
    """
    Health check — мгновенный ответ без обращения к БД.
    Используется Railway и load balancer для проверки живости приложения.
    """
    return JSONResponse({"status": "ok", "version": settings.app_version})


@app.get("/health/db")
async def health_db():
    """
    Deep health check — проверка подключения к PostgreSQL с таймаутом 3 сек.
    Быстро возвращает статус, не блокирует надолго при проблемах с БД.
    """
    from app.database import AsyncSessionLocal

    async def _check_db():
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))

    db_status: str
    try:
        await asyncio.wait_for(_check_db(), timeout=HEALTH_DB_TIMEOUT)
        db_status = "connected"
    except asyncio.TimeoutError:
        db_status = f"error: connection timeout ({HEALTH_DB_TIMEOUT}s)"
    except Exception as exc:
        db_status = f"error: {exc}"

    from app.core.lifespan import scheduler

    return JSONResponse(
        {
            "status": "ok" if db_status == "connected" else "degraded",
            "version": settings.app_version,
            "database": db_status,
            "scheduler": "running" if scheduler and scheduler.running else "stopped",
        }
    )
