from typing import Literal, get_args

from app.models import CustomModel


class ReceiptMessage(CustomModel):
    type: Literal["receipt"] = "receipt"
    prompt_id: str


class JobStatusMessage(CustomModel):
    type: Literal["job"] = "job"
    status: Literal["running", "cancelled"]


class JobQueuedMessage(CustomModel):
    type: Literal["job"] = "job"
    status: Literal["queued"] = "queued"
    position: int
    eta_seconds: int | None


class JobDoneMessage(CustomModel):
    type: Literal["job"] = "job"
    status: Literal["done"] = "done"
    images: list[str]


class JobErrorMessage(CustomModel):
    type: Literal["job"] = "job"
    status: Literal["error"] = "error"
    code: str


class ProgressMessage(CustomModel):
    type: Literal["progress"] = "progress"
    value: int | float | None
    max: int | float | None


class PreviewMessage(CustomModel):
    type: Literal["preview"] = "preview"
    mime: str | None
    data: str


class SystemMessage(CustomModel):
    type: Literal["system"] = "system"
    comfy_online: bool


# scripts/gen_ws_contract.py generates the frontend constants from here, so message types and job statuses are declared once.
# A new terminal state is one more Literal on a class below and nothing to copy anywhere else.

WS_MESSAGES: tuple[type[CustomModel], ...] = (
    ReceiptMessage,
    JobStatusMessage,
    JobQueuedMessage,
    JobDoneMessage,
    JobErrorMessage,
    ProgressMessage,
    PreviewMessage,
    SystemMessage,
)


def _literals(model: type[CustomModel], field: str) -> tuple[str, ...]:
    return get_args(model.model_fields[field].annotation)


def _unique(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


MESSAGE_TYPES = _unique(t for m in WS_MESSAGES for t in _literals(m, "type"))
JOB_STATUSES = _unique(
    s for m in WS_MESSAGES if "status" in m.model_fields for s in _literals(m, "status")
)
