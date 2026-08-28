from typing import Annotated

from fastapi import APIRouter, Path, Request, Response

from app import errors
from app.deps import RuntimeDep
from app.jobs.schemas import CancelRequest, GenerateRequest

router = APIRouter()


@router.post(
    "/generate",
    status_code=204,
    response_class=Response,
    tags=["jobs"],
    summary="Submit one generation",
    description="Validate the parameters, patch them into the workflow graph and submit to ComfyUI. Success returns no body; progress and results arrive over the WebSocket at /v1/ws. One IP can have only one job in flight at a time.",
    responses=errors.responses(400, 404, 422, 429, 502),
)
async def generate(body: GenerateRequest, request: Request, rt: RuntimeDep):
    assert request.client is not None
    await rt.jobs.submit(body, request.client.host)


@router.post(
    "/jobs/{promptId}/cancel",
    status_code=204,
    response_class=Response,
    tags=["jobs"],
    summary="Cancel a job",
    description="Cancel a queued or running job. A job that belongs to another session returns 404; an already finished job counts as cancelled and returns 204.",
    responses=errors.responses(404, 422, 502),
)
async def cancel(
    prompt_id: Annotated[str, Path(alias="promptId")],
    body: CancelRequest,
    rt: RuntimeDep,
):
    await rt.jobs.cancel(prompt_id, body.session_id)
