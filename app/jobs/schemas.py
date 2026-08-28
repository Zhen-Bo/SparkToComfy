from pydantic import Field

from app.models import RequestModel


class GenerateRequest(RequestModel):
    workflow_id: str
    session_id: str = Field(min_length=1, max_length=64)
    params: dict


class CancelRequest(RequestModel):
    session_id: str = Field(min_length=1, max_length=64)
