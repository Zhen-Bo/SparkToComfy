"""The parts every job component shares.

QueueMirror, JobEvents and JobsService all need comfy, db, registry and the rest, so they take one named bundle instead of eight parameters.
Runtime fills it in.
"""

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
