"""Admission and cancellation: only whether this request is allowed.

Event progression lives in app/jobs/events.py.
"""

import uuid

import httpx
from fastapi import HTTPException

from app.comfy.client import ComfyError
from app.database import JobSubmission, now
from app.errors import set_reason
from app.jobs import controls
from app.jobs.context import JobContext
from app.jobs.events import JobEvents
from app.jobs.models import Job
from app.jobs.queue import QueueMirror
from app.jobs.ratelimit import IpRateLimiter
from app.jobs.schemas import GenerateRequest
from app.ws import schemas as ws_schemas


class JobsService:
    def __init__(
        self,
        ctx: JobContext,
        queue: QueueMirror,
        events: JobEvents,
        limiter: IpRateLimiter,
    ) -> None:
        self.ctx = ctx
        self.queue = queue
        self.events = events
        self.limiter = limiter

    def _accept(self, body: GenerateRequest) -> tuple[dict, dict]:
        wf = self.ctx.catalog.get(body.workflow_id)
        if wf is None:
            set_reason(f"unknown workflow_id {body.workflow_id!r}")
            raise HTTPException(status_code=404, detail="not_found")
        try:
            values = controls.validate(wf["parameters"], body.params)
        except controls.InvalidControlValue as err:
            set_reason(str(err))
            raise HTTPException(status_code=400, detail="bad_request") from err
        if not self.queue.online:
            raise HTTPException(status_code=502, detail="comfyui_unreachable")
        seed_name, _ = controls.one_of_type(wf["parameters"], "seed")
        values[seed_name] = controls.resolve_seed(values[seed_name])
        return wf, values

    def _build_job(
        self, body: GenerateRequest, parameters: dict, values: dict, ip: str
    ) -> Job:
        size_name, size_control = controls.one_of_type(parameters, "size")
        width, height = controls.size_dims(size_control, values[size_name])
        seed_name, _ = controls.one_of_type(parameters, "seed")
        stored = dict(values)
        stored[seed_name] = str(stored[seed_name])
        return Job(
            submission=JobSubmission(
                prompt_id=str(uuid.uuid4()),
                session_id=body.session_id,
                workflow_id=body.workflow_id,
                params=stored,
                created_at=now(),
            ),
            ip=ip,
            size_key=(body.workflow_id, width * height),
            dims=(width, height),
            upscale=values["upscale"],
        )

    async def submit(self, body: GenerateRequest, ip: str) -> None:
        wf, values = self._accept(body)
        job = self._build_job(body, wf["parameters"], values, ip)
        active = self.ctx.registry.reserve_ip(job.ip, job.prompt_id)
        if active is not None:
            set_reason(f"{job.ip} already runs {active}")
            raise HTTPException(status_code=429, detail="job_active")
        self.ctx.registry.add_job(job)
        ok = False
        try:
            if not self.limiter.allows(job.ip):
                raise HTTPException(status_code=429, detail="rate_limited")
            prompt = controls.patch(wf["graph"], wf["parameters"], values)
            try:
                await self.ctx.comfy.submit_prompt(prompt, job.prompt_id)
            except ComfyError as err:
                set_reason(f"comfyui rejected the prompt: {err.payload}")
                raise HTTPException(status_code=400, detail="bad_request") from err
            except httpx.HTTPError as err:
                raise HTTPException(
                    status_code=502, detail="comfyui_unreachable"
                ) from err
            self.limiter.record(job.ip)
            ok = True
        finally:
            if not ok:
                self.ctx.registry.remove(job.prompt_id)
        await self.ctx.hub.send_to_session(
            job.submission.session_id,
            ws_schemas.ReceiptMessage(prompt_id=job.prompt_id),
        )
        await self.events.refresh_positions()

    async def cancel(self, prompt_id: str, session_id: str) -> None:
        job = self.ctx.registry.get(prompt_id)
        if job is None:
            if await self.ctx.db.has_done(session_id, prompt_id):
                return
            set_reason(f"job {prompt_id} is unknown to session {session_id}")
            raise HTTPException(status_code=404, detail="not_found")
        if job.submission.session_id != session_id:
            set_reason(f"job {prompt_id} belongs to another session")
            raise HTTPException(status_code=404, detail="not_found")
        job.cancelling = True
        try:
            await self.ctx.comfy.cancel_job(prompt_id)
        except httpx.HTTPError as err:
            raise HTTPException(status_code=502, detail="comfyui_unreachable") from err
