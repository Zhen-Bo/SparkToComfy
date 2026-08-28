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

    @property
    def prompt_id(self) -> str:
        return self.submission.prompt_id
