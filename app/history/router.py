from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from app import errors
from app.database import HISTORY_LIMIT
from app.deps import RuntimeDep
from app.history.schemas import HistoryItem
from app.images.urls import image_urls

router = APIRouter()

# The frontend reads the cap from this header instead of hardcoding its own 50.
LIMIT_HEADER = "X-History-Limit"


@router.get(
    "/history",
    response_model=list[HistoryItem],
    tags=["history"],
    summary="List the finished records of this session",
    description=(
        f"Return the {HISTORY_LIMIT} most recent finished records of this session, "
        f"newest first, excluding soft-deleted ones. The cap also comes back in the "
        f"{LIMIT_HEADER} response header."
    ),
    responses=errors.responses(422),
)
async def get_history(
    session_id: Annotated[str, Query(alias="sessionId")],
    response: Response,
    rt: RuntimeDep,
):
    response.headers[LIMIT_HEADER] = str(HISTORY_LIMIT)
    return [
        {**row, "images": image_urls(row["prompt_id"], row["images"])}
        for row in await rt.db.list_jobs(session_id)
    ]


@router.delete(
    "/history",
    status_code=204,
    tags=["history"],
    summary="Delete history records (soft delete)",
    description="Without promptId this clears every record of the session; with promptId it deletes only the given ones. If any promptId belongs to another session nothing is deleted and the call returns 404.",
    responses=errors.responses(404, 422),
)
async def delete_history(
    session_id: Annotated[str, Query(alias="sessionId")],
    rt: RuntimeDep,
    prompt_id: Annotated[list[str] | None, Query(alias="promptId")] = None,
):
    if prompt_id is None:
        await rt.db.clear_history(session_id)
    elif not await rt.db.delete_prompts(session_id, prompt_id):
        raise HTTPException(status_code=404, detail="not_found")
