"""Sole owner of process state.

lifespan builds one Runtime, routes reach it through app.deps.RuntimeDep, and every test builds its own.
"""

from dataclasses import dataclass
from pathlib import Path

from app.comfy.client import ComfyClient
from app.config import REGISTRY, SETTINGS, WorkflowCatalog
from app.database import Database
from app.jobs.context import JobContext
from app.jobs.eta import EtaModel
from app.jobs.events import JobEvents
from app.jobs.queue import QueueMirror
from app.jobs.ratelimit import IpRateLimiter
from app.jobs.registry import JobRegistry
from app.jobs.service import JobsService
from app.settings import ROOT
from app.ws.service import WsHub


@dataclass(slots=True)
class Runtime:
    ctx: JobContext
    queue: QueueMirror
    events: JobEvents
    jobs: JobsService

    # Shortcuts to the parts routes read most, so they need not spell out rt.ctx.xxx.
    @property
    def db(self) -> Database:
        return self.ctx.db

    @property
    def comfy(self) -> ComfyClient:
        return self.ctx.comfy

    @property
    def catalog(self) -> WorkflowCatalog:
        return self.ctx.catalog

    @property
    def registry(self) -> JobRegistry:
        return self.ctx.registry

    @property
    def hub(self) -> WsHub:
        return self.ctx.hub

    async def aclose(self) -> None:
        await self.hub.aclose()
        await self.comfy.aclose()
        await self.db.aclose()


def default_db_path() -> Path:
    return ROOT / SETTINGS.database


async def build(
    db_path: Path | str | None = None,
    comfy: ComfyClient | None = None,
    registry: Path = REGISTRY,
) -> Runtime:
    """Build every part and wire it together. Database migration completes before return."""
    db = Database(default_db_path() if db_path is None else db_path)
    await db.migrate()
    ctx = JobContext(
        comfy=ComfyClient() if comfy is None else comfy,
        db=db,
        catalog=WorkflowCatalog(registry),
        registry=JobRegistry(),
        eta=EtaModel(),
        hub=WsHub(),
    )
    queue = QueueMirror(ctx)
    events = JobEvents(ctx, queue)
    jobs = JobsService(ctx, queue, events, IpRateLimiter())
    return Runtime(ctx=ctx, queue=queue, events=events, jobs=jobs)
