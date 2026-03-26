import json
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import settings

logger = logging.getLogger(__name__)

UNWRAPPED_PATHS = {"/openapi.json", "/docs", "/redoc", "/health", "/ready", "/"}


def _cors_headers_from(response: Response) -> dict[str, str]:
    """Сохраняем CORS-заголовки при пересборке тела (CORSMiddleware добавляет их до обёртки)."""
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower().startswith("access-control-")
    }


def register_middleware(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,  # JWT in Authorization header; cookie cross-origin not required
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(response_wrapper_middleware)


async def response_wrapper_middleware(request: Request, call_next):
    if request.url.path in UNWRAPPED_PATHS:
        return await call_next(request)

    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error in middleware for %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": None, "message": "Internal server error"},
        )

    if not (
        response.status_code < 400
        and response.headers.get("content-type", "").startswith("application/json")
    ):
        return response

    # Read the streaming body into bytes
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, str):
            chunks.append(chunk.encode())
        else:
            chunks.append(chunk)
    body = b"".join(chunks)

    cors = _cors_headers_from(response)

    if not body:
        return Response(
            status_code=response.status_code,
            media_type="application/json",
            headers=cors,
        )

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        merged = {**dict(response.headers)}
        return Response(
            content=body,
            status_code=response.status_code,
            headers=merged,
            media_type="application/json",
        )

    # Wrap only if not already wrapped
    if not isinstance(data, dict) or "success" not in data:
        data = {"success": True, "data": data, "message": "Success"}

    return JSONResponse(
        content=data,
        status_code=response.status_code,
        headers=cors,
    )
