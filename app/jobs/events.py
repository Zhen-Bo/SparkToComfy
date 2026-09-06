"""Reconcile against ComfyUI's queue and history because terminal events can be lost.

Every terminal transition uses _claim so racing events and reconciliation cannot
both write a history row.
"""

import asyncio
import base64
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import structlog

from app.comfy.client import collect_images
from app.images.urls import image_urls
from app.jobs.config import RECONCILE
from app.jobs.context import JobContext
from app.jobs.models import Job
from app.jobs.queue import QueueMirror
from app.ws import schemas as ws_schemas

logger = structlog.stdlib.get_logger(__name__)

_CONNECTION_KINDS = frozenset({"disconnected", "connected", "status"})


class JobEvents:
    def __init__(self, ctx: JobContext, queue: QueueMirror) -> None:
        self.ctx = ctx
        self.queue = queue
        self._pass = asyncio.Lock()

    def _claim(self, pid: str) -> Job | None:
        """Grant one caller ownership of the history write and terminal message."""
        job = self.ctx.registry.remove(pid)
        if job is not None:
            self.ctx.eta.forget(pid)
        return job

    async def succeed(self, pid: str, hist: dict | None = None) -> None:
        if self.ctx.registry.get(pid) is None:
            return
        # Read before claiming so a failed fetch leaves the job available for retry.
        if hist is None:
            hist = await self.ctx.comfy.get_history(pid)
        job = self.ctx.registry.get(pid)
        if job is None:
            return
        self.ctx.eta.finish(job)
        self._claim(pid)
        seconds = (
            datetime.now(UTC) - datetime.fromisoformat(job.submission.created_at)
        ).total_seconds()
        logger.info("job done", prompt_id=pid, seconds=round(seconds, 1))
        images = collect_images(hist or {})
        await self.ctx.db.insert_finished(job.submission, "done", images=images)
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.JobDoneMessage(images=image_urls(pid, images)),
        )
        await self.refresh_positions()

    async def cancelled(self, pid: str) -> None:
        job = self._claim(pid)
        if job is None:
            return
        logger.info("job cancelled", prompt_id=pid)
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.JobStatusMessage(status="cancelled"),
        )

    async def fail(self, pid: str, code: str, message: str | None = None) -> None:
        job = self._claim(pid)
        if job is None:
            return
        message = message or code
        logger.error("job failed", prompt_id=pid, code=code, message=message)
        await self.ctx.db.insert_finished(job.submission, "error", error=message)
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.JobErrorMessage(code=code),
        )
        await self.refresh_positions()

    async def refresh_positions(self) -> None:
        """Skip overlapping passes, including callbacks from terminal transitions."""
        if self._pass.locked():
            return
        async with self._pass:
            await self._reconcile()

    async def _reconcile(self) -> None:
        present = await self.queue.observe()
        if present is None:
            return
        now = time.monotonic()
        for job in self.ctx.registry.all_jobs():
            if job.prompt_id in present:
                job.missing_since = None
                continue
            # Requested cancellation plus queue absence needs no grace period.
            if job.cancelling:
                await self.cancelled(job.prompt_id)
                continue
            if job.missing_since is None:
                job.missing_since = now
                continue
            if now - job.missing_since < RECONCILE.interval_seconds:
                continue
            await self._retire(job)

    async def _retire(self, job: Job) -> None:
        """Use history to settle a missing job, replaying recorded failure events."""
        pid = job.prompt_id
        hist = await self.ctx.comfy.get_history(pid)
        if not hist:
            await self.fail(pid, "job_lost", "ComfyUI no longer lists this job")
            return
        status = hist.get("status") or {}
        if status.get("status_str") == "success":
            logger.warning(
                "job finished without an event, settled from history", prompt_id=pid
            )
            await self.succeed(pid, hist)
            return
        for kind, data in status.get("messages") or []:
            if kind in ("execution_error", "execution_interrupted"):
                await _JOB_HANDLERS[kind](self, job, data)
                return
        await self.fail(pid, "execution_failed", "ComfyUI history shows no success")

    async def handle(self, kind: str, data: object) -> None:
        """A failed handler must not end the ComfyUI listener."""
        try:
            await self._handle(kind, data)
        except Exception:
            logger.exception("ComfyUI event failed", kind=kind)

    async def _handle(self, kind: str, data: object) -> None:
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
            n = len(self.ctx.registry.all_jobs())
            logger.warning("ComfyUI disconnected, failing jobs in flight", jobs=n)
            for job in self.ctx.registry.all_jobs():
                await self.fail(job.prompt_id, "comfyui_offline")
            await self.ctx.hub.send_to_all(ws_schemas.SystemMessage(comfy_online=False))
            return
        if kind == "connected" and not self.queue.online:
            self.queue.online = True
            logger.info("ComfyUI connected")
            await self.ctx.hub.send_to_all(ws_schemas.SystemMessage(comfy_online=True))
        await self.refresh_positions()

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
