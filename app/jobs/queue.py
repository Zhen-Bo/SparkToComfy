"""HTTP and WebSocket readers share a mirror instead of querying ComfyUI's queue."""

from app.jobs.context import JobContext
from app.ws import schemas as ws_schemas


class QueueMirror:
    def __init__(self, ctx: JobContext) -> None:
        self.ctx = ctx
        self.online = False
        self.slots: dict[str, tuple[int, int | None]] = {}

    def slot(self, prompt_id: str) -> tuple[int, int | None] | None:
        return self.slots.get(prompt_id)

    async def mark_running(self, job) -> None:
        """Repeated observations must not resend the running transition."""
        if job.status == "running":
            return
        job.status = "running"
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.JobStatusMessage(status="running"),
        )

    async def observe(self) -> frozenset[str] | None:
        """Return listed prompt IDs after updating positions and ETA.

        None means the queue was not read, not that it is empty; do not retire jobs.
        """
        if not self.online or not self.ctx.registry.all_jobs():
            return None
        queue = await self.ctx.comfy.get_queue()
        running = queue.get("queue_running") or []
        pending = sorted(queue.get("queue_pending") or [], key=lambda it: it[0])
        items = [*running, *pending]
        n_running = len(running)
        ahead = 0.0
        foreign_ahead = False
        mirror: dict[str, tuple[int, int | None]] = {}
        for index, item in enumerate(items):
            pid = item[1]
            job = self.ctx.registry.get(pid)
            if job is None:
                foreign_ahead = True
                continue
            if index < n_running:
                await self.mark_running(job)
            else:
                position = max(1, index)
                eta_seconds = None if foreign_ahead else round(ahead)
                mirror[pid] = (position, eta_seconds)
                await self.ctx.hub.send_to_session(
                    job.submission.session_id,
                    ws_schemas.JobQueuedMessage(
                        position=position,
                        eta_seconds=eta_seconds,
                    ),
                )
            ahead += self.ctx.eta.expected(job)
        self.slots = mirror
        return frozenset(item[1] for item in items)
