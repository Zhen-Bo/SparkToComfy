"""Estimate the time left in the queue.

Each size class keeps its 5 most recent measured durations, and upscaling adds a separate surcharge on top.
"""

import time
from collections import deque

from app.jobs.config import ETA
from app.jobs.models import Job

UPSCALE_SECONDS_PER_MEGAPIXEL = ETA.upscale_seconds_per_megapixel
COLD_START_SECONDS = 30.0
SAMPLES = 5


class EtaModel:
    def __init__(self) -> None:
        self._started: dict[str, float] = {}
        self._durations: dict[tuple[str, int], deque[float]] = {}

    def start(self, prompt_id: str) -> None:
        self._started[prompt_id] = time.monotonic()

    def forget(self, prompt_id: str) -> None:
        self._started.pop(prompt_id, None)

    def _class_avg(self, key: tuple[str, int]) -> float:
        samples = self._durations.get(key)
        if not samples:
            return COLD_START_SECONDS
        return sum(samples) / len(samples)

    def _surcharge(self, job: Job) -> float:
        upscale = job.upscale
        if upscale <= 1:
            return 0.0
        width, height = job.dims
        return UPSCALE_SECONDS_PER_MEGAPIXEL * width * height * upscale**2 / 1e6

    def finish(self, job: Job) -> None:
        t0 = self._started.pop(job.prompt_id, None)
        if t0 is None:
            return
        sample = time.monotonic() - t0 - self._surcharge(job)
        if sample > 0:
            self._durations.setdefault(job.size_key, deque(maxlen=SAMPLES)).append(
                sample
            )

    def expected(self, job: Job) -> float:
        return self._class_avg(job.size_key) + self._surcharge(job)
