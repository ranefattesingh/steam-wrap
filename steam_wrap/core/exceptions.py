"""Domain exceptions and their HTTP translation.

Every error leaves the API in one shape::

    {"error": {"code": "invalid_token", "message": "...", "request_id": "..."}}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that map cleanly to an HTTP response."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: Any = None) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


class InvalidTokenError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_token"
    message = "The Steam access token is missing, malformed or expired."


class SteamAuthError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "steam_auth_failed"
    message = "Steam rejected the access token."


class GameNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "game_not_found"
    message = "The game is not in this user's library."


class SteamRateLimitedError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "steam_rate_limited"
    message = "Steam is rate limiting requests. Try again shortly."


class SteamUnavailableError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "steam_unavailable"
    message = "Steam returned an error or could not be reached."


def _error_body(request: Request, code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that render all errors in the common envelope."""

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.warning("%s: %s", exc.code, exc.message)
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            _error_body(request, exc.code, exc.message, exc.details),
            status_code=exc.status_code,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            _error_body(request, "validation_error", "Invalid request parameters.", details),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(
            _error_body(request, code, str(exc.detail)),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            _error_body(request, AppError.code, AppError.message),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
