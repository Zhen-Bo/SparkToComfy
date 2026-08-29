from typing import Literal

from pydantic import Field

from app.models import CustomModel, RequestModel


class GenerateRequest(RequestModel):
    workflow_id: str
    session_id: str = Field(min_length=1, max_length=64)
    params: dict


class CancelRequest(RequestModel):
    session_id: str = Field(min_length=1, max_length=64)


class GenerateResponse(CustomModel):
    prompt_id: str


class JobStatusResponse(CustomModel):
    status: Literal["queued", "running", "done", "error"]
    images: list[str] = []  # done only
    error: str | None = None  # error only
