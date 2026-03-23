import json
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import settings

logger = logging.getLogger(__name__)

UNWRAPPED_PATHS = {"/openapi.json", "/docs", "/redoc", "/health", "/health/db", "/"}


def register_middleware(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
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

    if not body:
        return Response(status_code=response.status_code, media_type="application/json")

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json",
        )

    # Wrap only if not already wrapped
    if not isinstance(data, dict) or "success" not in data:
        data = {"success": True, "data": data, "message": "Success"}

    return JSONResponse(content=data, status_code=response.status_code)
