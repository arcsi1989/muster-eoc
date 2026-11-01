"""Domain exceptions. `api/error_handlers.py` maps them to status codes (CODING_STANDARDS B6)."""


class AppError(Exception):
    status = 500
    code = "internal"


class NotFound(AppError):
    status = 404
    code = "not_found"


class DataNotLoaded(AppError):
    """Reference data the app needs is missing from the database (startup load failed)."""

    code = "data_not_loaded"


class ConflictError(AppError):
    status = 409
    code = "conflict"
