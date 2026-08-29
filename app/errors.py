import secrets

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.models import CustomModel

logger = structlog.stdlib.get_logger(__name__)

CODES = {
    "bad_request",
    "not_found",
    "method_not_allowed",
    "unprocessable_content",
    "job_active",
    "rate_limited",
    "internal_error",
    "comfyui_unreachable",
}

_BY_STATUS = {
    400: "bad_request",
    404: "not_found",
    405: "method_not_allowed",
    422: "unprocessable_content",
    429: "rate_limited",
    502: "comfyui_unreachable",
}


class ErrorResponse(CustomModel):
    code: str
    request_id: str


_DESC = {
    400: "Invalid parameters or workflow declaration",
    404: "The resource does not exist, or does not belong to this session",
    422: "The request body does not match the schema",
    429: "The same IP already has a job running (job_active), or the rate limit is exceeded (rate_limited)",
    502: "ComfyUI is unreachable",
}


def responses(*codes: int) -> dict[int | str, dict]:
    return {c: {"model": ErrorResponse, "description": _DESC[c]} for c in codes}


def set_reason(reason: str) -> None:
    """Attach the cause of a rejection to every log line of this request."""
    structlog.contextvars.bind_contextvars(reason=reason)


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # One connection serves many requests in turn, so the context is reset here, not only set.
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(
                request_id="req_" + secrets.token_hex(6)
            )
        await self.app(scope, receive, send)


def _code(status_code: int, detail: object) -> str:
    if isinstance(detail, str) and detail in CODES:
        return detail
    return _BY_STATUS.get(status_code, "internal_error")


def _respond(status_code: int, code: str) -> JSONResponse:
    body = ErrorResponse(
        code=code,
        request_id=structlog.contextvars.get_contextvars().get("request_id", "-"),
    )
    return JSONResponse(body.model_dump(by_alias=True), status_code=status_code)


def _fields(request: Request, status_code: int, code: str) -> dict[str, object]:
    return {
        "status": status_code,
        "code": code,
        "method": request.method,
        "path": request.url.path,
    }


async def _on_http(request: Request, exc: Exception) -> JSONResponse:
    status_code = exc.status_code if isinstance(exc, StarletteHTTPException) else 500
    detail = exc.detail if isinstance(exc, StarletteHTTPException) else None
    code = _code(status_code, detail)
    log = logger.error if status_code >= 500 else logger.warning
    log("request failed", **_fields(request, status_code, code))
    return _respond(status_code, code)


async def _on_validation(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, RequestValidationError):
        # pydantic puts the offending value in each error, so only location and type may be logged.
        set_reason(str([(e.get("loc"), e.get("type")) for e in exc.errors()]))
        logger.debug("invalid request body", errors=exc.errors())
    logger.warning("request failed", **_fields(request, 422, "unprocessable_content"))
    return _respond(422, "unprocessable_content")


async def _on_unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("request failed", **_fields(request, 500, "internal_error"))
    return _respond(500, "internal_error")


def install(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(StarletteHTTPException, _on_http)
    app.add_exception_handler(RequestValidationError, _on_validation)
    app.add_exception_handler(Exception, _on_unhandled)
