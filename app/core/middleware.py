import json
import logging
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(f"🔄 {request.method} {request.url.path} - Started")
        
        try:
            response = await call_next(request)
            
            # Calculate response time
            process_time = time.time() - start_time
            
            # Log response
            status_emoji = "✅" if response.status_code < 400 else "❌"
            logger.info(
                f"{status_emoji} {request.method} {request.url.path} - "
                f"Status: {response.status_code} - Time: {process_time:.3f}s"
            )
            
            # Add timing header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"💥 {request.method} {request.url.path} - "
                f"Error: {str(e)} - Time: {process_time:.3f}s",
                exc_info=True
            )
            raise


def register_middleware(app: FastAPI):
    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add response wrapper middleware
    app.middleware("http")(response_wrapper_middleware)


# Paths that must not be wrapped (OpenAPI/Swagger need raw JSON)
UNWRAPPED_PATHS = {"/openapi.json", "/docs", "/redoc"}


async def response_wrapper_middleware(request: Request, call_next):
    if request.url.path in UNWRAPPED_PATHS:
        return await call_next(request)

    response = await call_next(request)
    if (
        response.status_code < 400
        and response.headers.get("content-type", "").startswith("application/json")
    ):
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        try:
            data = json.loads(body.decode())
            if not isinstance(data, dict) or "success" not in data:
                wrapped_data = {"success": True, "data": data, "message": "Success"}
                body = json.dumps(wrapped_data).encode()
        except Exception as e:
            logger.warning("Response wrap failed for %s: %s", request.url.path, e)
        headers = {
            k: v for k, v in response.headers.items() if k.lower() != "content-length"
        }
        try:
            content = json.loads(body.decode()) if body else None
        except Exception as e:
            logger.error("Response JSON parse failed for %s: %s", request.url.path, e)
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json",
            )
        return JSONResponse(
            content=content,
            status_code=response.status_code,
            headers=headers,
        )
    return response
