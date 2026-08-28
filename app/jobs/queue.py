"""Mirror of the ComfyUI queue: who runs, who waits where, how long is left.

Only ComfyUI events advance it.
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
        job.status = "running"
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.JobStatusMessage(status="running"),
        )

    async def refresh(self) -> tuple[str, ...]:
        """Recompute every job position and ETA.

        Return the prompt_id of each job that was cancelled and has left the queue.
        """
        if not self.online or not self.ctx.registry.all_jobs():
            return ()
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
        present = {item[1] for item in items}
        return tuple(
            job.prompt_id
            for job in self.ctx.registry.all_jobs()
            if job.cancelling and job.prompt_id not in present
        )
