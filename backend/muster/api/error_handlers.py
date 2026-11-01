"""Maps exceptions to the one error body (CODING_STANDARDS B6): {"error": {"code", "message"}}.

Kept out of `muster.errors` so the domain packages that raise those exceptions never import
FastAPI (B1).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from muster.errors import AppError

log = logging.getLogger(__name__)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status, exc.code, str(exc))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        return _error(422, "validation_error", f"{where}: {first.get('msg', 'invalid request')}")

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # A bug, not a refusal: details go to the server log, never to the client (B6, B7).
        log.exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return _error(500, "internal", "internal error")
