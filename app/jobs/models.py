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
    # First absence in monotonic seconds; None while listed. Use elapsed time because
    # passes can burst before ComfyUI finishes accepting a submitted job.
    missing_since: float | None = None

    @property
    def prompt_id(self) -> str:
        return self.submission.prompt_id
