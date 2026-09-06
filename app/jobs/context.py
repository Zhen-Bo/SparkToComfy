from dataclasses import dataclass

from app.comfy.client import ComfyClient
from app.config import WorkflowCatalog
from app.database import Database
from app.jobs.eta import EtaModel
from app.jobs.registry import JobRegistry
from app.ws.service import WsHub


@dataclass(slots=True)
class JobContext:
    comfy: ComfyClient
    db: Database
    catalog: WorkflowCatalog
    registry: JobRegistry
    eta: EtaModel
    hub: WsHub
