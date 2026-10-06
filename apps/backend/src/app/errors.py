from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _body(request: Request, code: str, message: str, details: object = None) -> dict[str, object]:
    err: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        err["details"] = details
    return {"error": err}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(request, exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]} for e in exc.errors()
        ]
        return JSONResponse(
            _body(request, "validation_error", "request validation failed", details),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            _body(request, f"http_{exc.status_code}", str(exc.detail)), status_code=exc.status_code
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        import logging

        logging.getLogger("app").exception(
            "unhandled error", extra={"request_id": getattr(request.state, "request_id", None)}
        )
        return JSONResponse(_body(request, "internal_error", "internal server error"), status_code=500)


def translate_deletion_error(exc: Exception) -> ApiError | None:
    """Map `app.deletion` exceptions to API errors (ADR-0014 §7.6); None for anything else."""
    import logging

    from app import deletion

    if isinstance(exc, deletion.HasActiveJobsError):
        return ApiError(409, "has_active_jobs", f"{exc}")
    if isinstance(exc, deletion.HasResultsError):
        return ApiError(409, "has_results", f"{exc}")
    if isinstance(exc, deletion.NeedsCascadeError):
        return ApiError(409, "needs_cascade", f"{exc}")
    if isinstance(exc, deletion.StillReferencedError):
        logging.getLogger("app").warning("deletion refused: still referenced (%s)", exc.constraint)
        return ApiError(409, "still_referenced", "a row that references this target still exists")
    if isinstance(exc, deletion.RetryLaterError):
        return ApiError(
            503, "retry_later", "the operation could not complete under contention; retry shortly"
        )
    if isinstance(exc, deletion.IntegrityFailureError):
        # SQLSTATE and constraint are logged; the client gets no SQL detail
        logging.getLogger("app").error(
            "integrity error: SQLSTATE %s constraint %s", exc.state, exc.constraint
        )
        return ApiError(500, "integrity_error", "an unexpected integrity error occurred")
    return None
