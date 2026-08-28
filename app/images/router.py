from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from app import errors
from app.deps import RuntimeDep

router = APIRouter()
CHUNK = 64 * 1024


@router.get(
    "/images/{promptId}",
    response_class=StreamingResponse,
    tags=["images"],
    summary="Get an output image (streamed through from ComfyUI)",
    description="index selects which output of the job to return, default 0. The bytes never touch this service's disk; they are streamed straight through.",
    responses={
        200: {"content": {"image/*": {}}, "description": "Image bytes"},
        **errors.responses(404, 422, 502),
    },
)
async def get_image(
    prompt_id: Annotated[str, Path(alias="promptId")],
    rt: RuntimeDep,
    index: Annotated[int, Query(ge=0)] = 0,
):
    ref = await rt.db.get_image_ref(prompt_id, index)
    if ref is None:
        raise HTTPException(status_code=404, detail="not_found")
    try:
        upstream = await rt.comfy.stream_view(ref)
    except httpx.HTTPStatusError as err:
        if err.response.status_code == 404:
            raise HTTPException(status_code=404, detail="not_found") from err
        raise HTTPException(status_code=502, detail="comfyui_unreachable") from err
    except httpx.RequestError as err:
        raise HTTPException(status_code=502, detail="comfyui_unreachable") from err

    async def stream():
        try:
            async for chunk in upstream.aiter_bytes(CHUNK):
                yield chunk
        finally:
            await upstream.aclose()

    return StreamingResponse(
        stream(),
        media_type=upstream.headers.get("Content-Type", "application/octet-stream"),
        headers={"Content-Disposition": f'inline; filename="{ref["filename"]}"'},
    )
