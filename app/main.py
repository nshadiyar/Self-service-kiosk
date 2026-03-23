"""
FastAPI application — быстрый startup для Railway (устраняет 502).

- / и /health — мгновенный ответ, без БД
- /ready — readiness check: проверка БД через AsyncSessionLocal (SELECT 1, таймаут 3 сек)
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


@app.get("/ready")
async def ready():
    """
    Readiness probe: проверка БД через AsyncSessionLocal (SELECT 1), таймаут 3 сек.
    status: ok — БД доступна, status: degraded — БД недоступна.
    """
    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=3)
        return JSONResponse(
            {"status": "ok", "database": "ok"},
            status_code=200,
        )
    except Exception as e:
        return JSONResponse(
            {"status": "degraded", "database": str(e)},
            status_code=503,
        )
