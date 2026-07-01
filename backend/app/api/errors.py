"""
Structured API error responses.
"""
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_429_TOO_MANY_REQUESTS

from app.api.schemas import ErrorDetail, ErrorResponse

log = structlog.get_logger()

_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}


def _error_code(status_code: int) -> str:
    return _STATUS_CODES.get(status_code, "ERROR")


def _error_body(status_code: int, message: str) -> dict:
    return ErrorResponse(
        error=ErrorDetail(code=_error_code(status_code), message=message)
    ).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.status_code, message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError):
        messages = [
            f"{'.'.join(str(p) for p in err.get('loc', []))}: {err.get('msg', 'invalid')}"
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(HTTP_422_UNPROCESSABLE_ENTITY, "; ".join(messages)),
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(_request: Request, _exc: RateLimitExceeded):
        return JSONResponse(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            content=_error_body(HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        log.exception("api.unhandled_error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content=_error_body(500, "Internal server error"),
        )
