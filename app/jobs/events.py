"""ComfyUI event to job lifecycle to database write plus WebSocket push.

Dispatch uses a table instead of an if/elif chain, so a new protocol event is one more row in the table.
"""

import base64
import logging
from collections.abc import Awaitable, Callable

from app.comfy.client import collect_images
from app.images.urls import image_urls
from app.jobs.context import JobContext
from app.jobs.models import Job
from app.jobs.queue import QueueMirror
from app.ws import schemas as ws_schemas

logger = logging.getLogger(__name__)

_CONNECTION_KINDS = frozenset({"disconnected", "connected", "status"})


class JobEvents:
    def __init__(self, ctx: JobContext, queue: QueueMirror) -> None:
        self.ctx = ctx
        self.queue = queue

    # --- terminal states ---

    def _release(self, pid: str) -> None:
        self.ctx.eta.forget(pid)
        self.ctx.registry.remove(pid)

    async def succeed(self, pid: str, hist: dict | None = None) -> None:
        job = self.ctx.registry.get(pid)
        if job is None:
            return
        self.ctx.eta.finish(job)
        if hist is None:
            hist = await self.ctx.comfy.get_history(pid)
        images = collect_images(hist or {})
        await self.ctx.db.insert_finished(job.submission, "done", images=images)
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.JobDoneMessage(images=image_urls(pid, images)),
        )
        self._release(pid)
        await self.refresh_positions()

    async def cancelled(self, pid: str) -> None:
        job = self.ctx.registry.get(pid)
        if job is None:
            return
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.JobStatusMessage(status="cancelled"),
        )
        self._release(pid)

    async def fail(self, pid: str, code: str, message: str | None = None) -> None:
        job = self.ctx.registry.get(pid)
        if job is None:
            return
        message = message or code
        logger.error("job %s failed: %s (%s)", pid, message, code)
        await self.ctx.db.insert_finished(job.submission, "error", error=message)
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.JobErrorMessage(code=code),
        )
        self._release(pid)
        await self.refresh_positions()

    async def refresh_positions(self) -> None:
        for pid in await self.queue.refresh():
            await self.cancelled(pid)

    # --- event entry point ---

    async def handle(self, kind: str, data: object) -> None:
        if kind in _CONNECTION_KINDS:
            await self._on_connection(kind)
            return
        if not isinstance(data, dict):
            return
        pid = data.get("prompt_id")
        job = self.ctx.registry.get(pid) if pid else None
        handler = _JOB_HANDLERS.get(kind)
        if job is None or handler is None:
            return
        await handler(self, job, data)

    async def _on_connection(self, kind: str) -> None:
        if kind == "disconnected":
            self.queue.slots = {}
            if not self.queue.online:
                return
            self.queue.online = False
            for job in self.ctx.registry.all_jobs():
                await self.fail(job.prompt_id, "comfyui_offline")
            await self.ctx.hub.send_to_all(ws_schemas.SystemMessage(comfy_online=False))
            return
        if kind == "connected" and not self.queue.online:
            self.queue.online = True
            await self.ctx.hub.send_to_all(ws_schemas.SystemMessage(comfy_online=True))
        await self.refresh_positions()

    # --- one handler per event ---

    async def _on_start(self, job: Job, data: dict) -> None:
        self.ctx.eta.start(job.prompt_id)
        await self.queue.mark_running(job)

    async def _on_progress(self, job: Job, data: dict) -> None:
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.ProgressMessage(value=data.get("value"), max=data.get("max")),
        )

    async def _on_preview(self, job: Job, data: dict) -> None:
        raw = data.get("bytes", b"")
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.PreviewMessage(
                mime=data.get("image_type"),
                data=base64.b64encode(raw).decode("ascii"),
            ),
        )

    async def _on_success(self, job: Job, data: dict) -> None:
        await self.succeed(job.prompt_id)

    async def _on_error(self, job: Job, data: dict) -> None:
        await self.fail(
            job.prompt_id,
            "execution_failed",
            data.get("exception_message") or "error",
        )

    async def _on_interrupted(self, job: Job, data: dict) -> None:
        if not job.cancelling:
            await self.fail(job.prompt_id, "interrupted")
            return
        await self.cancelled(job.prompt_id)
        await self.refresh_positions()


_JOB_HANDLERS: dict[str, Callable[[JobEvents, Job, dict], Awaitable[None]]] = {
    "execution_start": JobEvents._on_start,
    "progress": JobEvents._on_progress,
    "preview": JobEvents._on_preview,
    "execution_success": JobEvents._on_success,
    "execution_error": JobEvents._on_error,
    "execution_interrupted": JobEvents._on_interrupted,
}
