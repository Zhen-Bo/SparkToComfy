import logging
import secrets
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.models import CustomModel

logger = logging.getLogger(__name__)

REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")
REASON: ContextVar[str] = ContextVar("reason", default="")

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
    REASON.set(reason)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID.get()
        return True


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            REQUEST_ID.set("req_" + secrets.token_hex(6))
            REASON.set("")
        await self.app(scope, receive, send)


def _code(status_code: int, detail: object) -> str:
    if isinstance(detail, str) and detail in CODES:
        return detail
    return _BY_STATUS.get(status_code, "internal_error")


def _respond(status_code: int, code: str) -> JSONResponse:
    body = ErrorResponse(code=code, request_id=REQUEST_ID.get())
    return JSONResponse(body.model_dump(by_alias=True), status_code=status_code)


def _line(request: Request, status_code: int, code: str) -> str:
    reason = REASON.get()
    line = f"{status_code} {code} {request.method} {request.url.path}"
    return f"{line} — {reason}" if reason else line


async def _on_http(request: Request, exc: Exception) -> JSONResponse:
    status_code = exc.status_code if isinstance(exc, StarletteHTTPException) else 500
    detail = exc.detail if isinstance(exc, StarletteHTTPException) else None
    code = _code(status_code, detail)
    log = logger.error if status_code >= 500 else logger.warning
    log(_line(request, status_code, code))
    return _respond(status_code, code)


async def _on_validation(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, RequestValidationError):
        set_reason(str(exc.errors()))
    logger.warning(_line(request, 422, "unprocessable_content"))
    return _respond(422, "unprocessable_content")


async def _on_unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(_line(request, 500, "internal_error"))
    return _respond(500, "internal_error")


def install(app: FastAPI) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdFilter())
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(StarletteHTTPException, _on_http)
    app.add_exception_handler(RequestValidationError, _on_validation)
    app.add_exception_handler(Exception, _on_unhandled)
