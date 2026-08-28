from collections.abc import Mapping

import httpx
from fastapi import APIRouter, HTTPException, Response

from app import errors
from app.deps import RuntimeDep
from app.jobs import controls

router = APIRouter()

CACHE_SECONDS = 3600


def _allowed_files(workflows: Mapping[str, dict]) -> set[str]:
    names: set[str] = set()
    for wf in workflows.values():
        for _, control in controls.all_of_type(wf["parameters"], "lora"):
            names.update(control["options"])
    return names


@router.get(
    "/lora/cover",
    response_class=Response,
    tags=["lora"],
    summary="Get a LoRA cover image",
    description="Only file names allowed by the current workflow declarations are accepted. Returns 404 when ComfyUI does not know the LoRA, or when it has no cover.",
    responses={
        200: {"content": {"image/*": {}}, "description": "Cover image bytes"},
        **errors.responses(404, 422, 502),
    },
)
async def get_cover(lora: str, rt: RuntimeDep):
    if lora not in _allowed_files(rt.catalog.all()):
        raise HTTPException(status_code=404, detail="not_found")
    try:
        items = await rt.comfy.list_loras()
        match = next((it for it in items if it.get("file_name") == lora), None)
        if match is None or match.get("preview_url", "") == "":
            raise HTTPException(status_code=404, detail="not_found")
        data, ctype = await rt.comfy.fetch_preview(match["preview_url"])
    except httpx.HTTPStatusError as err:
        if err.response.status_code == 404:
            raise HTTPException(status_code=404, detail="not_found") from err
        raise HTTPException(status_code=502, detail="comfyui_unreachable") from err
    except httpx.RequestError as err:
        raise HTTPException(status_code=502, detail="comfyui_unreachable") from err
    return Response(
        content=data,
        media_type=ctype,
        headers={"Cache-Control": f"public, max-age={CACHE_SECONDS}"},
    )
