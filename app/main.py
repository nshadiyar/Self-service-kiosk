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
    """Root — instant response, no DB."""
    return JSONResponse({"status": "ok", "version": settings.app_version})


@app.get("/health")
async def health_check():
    """Health check — instant response, no DB."""
    return JSONResponse({"status": "ok", "version": settings.app_version})


@app.get("/health/db")
async def health_db():
    """Deep health check — tests database connectivity."""
    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = f"error: {exc}"

    from app.core.lifespan import scheduler

    return JSONResponse({
        "status": "ok" if "connected" in db_status else "degraded",
        "version": settings.app_version,
        "database": db_status,
        "scheduler": "running" if scheduler and scheduler.running else "stopped",
    })
