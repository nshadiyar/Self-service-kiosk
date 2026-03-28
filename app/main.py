"""
FastAPI application — быстрый startup для Railway (устраняет 502).

- / и /health — мгновенный ответ, без БД
- /ready — readiness check: проверка БД через AsyncSessionLocal (SELECT 1, таймаут 3 сек)
"""
import asyncio
import os
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
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
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True},
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


def custom_openapi():
    """OpenAPI: кнопка Authorize в Swagger (Bearer JWT) для защищённых эндпоинтов."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=getattr(app, "openapi_version", "3.1.0"),
        description=app.description,
        routes=app.routes,
    )
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Access token из POST /api/v1/auth/login (поле access_token). Вставь только токен, без префикса Bearer.",
    }
    public_routes = {
        ("/", "get"),
        ("/health", "get"),
        ("/ready", "get"),
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/refresh", "post"),
    }
    for path, path_item in openapi_schema.get("paths", {}).items():
        for method in ("get", "post", "put", "patch", "delete"):
            if method not in path_item:
                continue
            if (path, method) in public_routes:
                continue
            path_item[method].setdefault("security", []).append({"BearerAuth": []})
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
