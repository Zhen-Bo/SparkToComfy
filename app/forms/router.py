from fastapi import APIRouter

from app.deps import RuntimeDep
from app.forms.schemas import WorkflowItem
from app.forms.service import project_section

router = APIRouter()


@router.get(
    "/workflows",
    response_model=list[WorkflowItem],
    response_model_exclude_none=True,
    tags=["forms"],
    summary="List every workflow and its parameter form",
    description="One page-load call that returns the summary and parameter form of every workflow. The content is declared in config/parameter/*.yaml and a background task reloads it every 30 seconds.",
)
async def list_workflows(rt: RuntimeDep):
    """Send the whole page-load payload at once: summary plus parameter form."""
    return [
        {
            "id": wid,
            "name": w["name"],
            "parameters": {
                "basic": project_section(w["parameters"]["basic"]),
                "advanced": project_section(w["parameters"]["advanced"]),
            },
        }
        for wid, w in rt.catalog.all().items()
    ]
