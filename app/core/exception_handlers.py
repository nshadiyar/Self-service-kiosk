from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import logging

from app.core.exceptions import BromartException

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI):
    app.exception_handler(BromartException)(bromart_exception_handler)
    app.exception_handler(HTTPException)(http_exception_handler)
    app.exception_handler(Exception)(general_exception_handler)


async def bromart_exception_handler(request: Request, exc: BromartException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "data": None, "message": exc.detail},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "data": None, "message": exc.detail},
    )


async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "message": "Internal server error"},
    )
