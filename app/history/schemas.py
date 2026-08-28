from datetime import datetime

from app.models import CustomModel


class HistoryItem(CustomModel):
    workflow_id: str
    prompt_id: str
    params: dict
    images: list[str]
    created_at: datetime
    finished_at: datetime
