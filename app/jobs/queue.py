"""Mirror of the ComfyUI queue: who runs, who waits where, how long is left.

ComfyUI events advance it, and observe() corrects it against the real queue.
HTTP requests and new WebSocket connections read the mirror instead of asking ComfyUI for its queue.
"""

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
        """Announce the transition into running, once. observe() runs on every pass and would
        otherwise resend running for the whole life of the job."""
        if job.status == "running":
            return
        job.status = "running"
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.JobStatusMessage(status="running"),
        )

    async def observe(self) -> frozenset[str] | None:
        """Read the ComfyUI queue, recompute every job position and ETA.

        Return the prompt_id of every job ComfyUI lists, or None when the queue was not read.
        None is not an empty queue: on None nothing may be concluded about a missing job.
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
