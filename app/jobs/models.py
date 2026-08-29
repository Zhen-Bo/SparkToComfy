from dataclasses import dataclass
from typing import Literal

from app.database import JobSubmission


@dataclass(slots=True)
class Job:
    submission: JobSubmission
    ip: str
    size_key: tuple[str, int]
    dims: tuple[int, int]
    upscale: float
    status: Literal["queued", "running"] = "queued"
    cancelling: bool = False
    # time.monotonic() of the first reconcile pass that found this job unlisted; None while listed.
    # Absence is measured in time, not in passes: passes arrive in bursts (a finished job triggers
    # several within milliseconds), and a job is unlisted while ComfyUI is still accepting it.
    missing_since: float | None = None

    @property
    def prompt_id(self) -> str:
        return self.submission.prompt_id
