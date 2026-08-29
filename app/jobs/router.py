from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response

from app import errors
from app.deps import RuntimeDep
from app.images.urls import image_urls
from app.jobs.schemas import (
    CancelRequest,
    GenerateRequest,
    GenerateResponse,
    JobStatusResponse,
)

router = APIRouter()


@router.post(
    "/generate",
    response_model=GenerateResponse,
    tags=["jobs"],
    summary="Submit one generation",
    description="Validate the parameters, patch them into the workflow graph and submit to ComfyUI. The response carries the prompt id; progress and results arrive over the WebSocket at /v1/ws. One IP can have only one job in flight at a time.",
    responses=errors.responses(400, 404, 422, 429, 502),
)
async def generate(body: GenerateRequest, request: Request, rt: RuntimeDep):
    assert request.client is not None
    return GenerateResponse(prompt_id=await rt.jobs.submit(body, request.client.host))


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


@router.get(
    "/jobs/{promptId}",
    response_model=JobStatusResponse,
    tags=["jobs"],
    summary="Read where one job stands",
    description="queued or running while the job is in flight; done with its images or error with the reason once it finished. A cancelled job leaves no record and answers 404, as does a job of another session.",
    responses=errors.responses(404, 422),
)
async def job_status(
    prompt_id: Annotated[str, Path(alias="promptId")],
    session_id: Annotated[str, Query(alias="sessionId")],
    rt: RuntimeDep,
):
    job = rt.registry.get(prompt_id)
    if job is not None and job.submission.session_id == session_id:
        return JobStatusResponse(status=job.status)
    # A finishing job leaves the registry one database write before its record exists
    # (app/jobs/events.py); a query inside that window reads 404, the same as a cancel.
    row = await rt.db.get_job(session_id, prompt_id)
    if row is None:
        errors.set_reason(f"job {prompt_id} is unknown to session {session_id}")
        raise HTTPException(status_code=404, detail="not_found")
    return JobStatusResponse(
        status=row["status"],
        images=image_urls(prompt_id, row["images"]),
        error=row["error"],
    )
