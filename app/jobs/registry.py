"""Jobs in flight. One per Runtime rather than one per process, so every test gets a clean one."""

from app.jobs.models import Job


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._active_ip: dict[str, str] = {}

    def reserve_ip(self, ip: str, prompt_id: str) -> str | None:
        active = self._active_ip.get(ip)
        if active is not None:
            return active
        self._active_ip[ip] = prompt_id
        return None

    def release_ip(self, ip: str, prompt_id: str) -> None:
        if self._active_ip.get(ip) == prompt_id:
            self._active_ip.pop(ip)

    def add_job(self, job: Job) -> None:
        if self._active_ip.get(job.ip) != job.prompt_id:
            raise RuntimeError("job IP is not reserved by prompt")
        self._jobs[job.prompt_id] = job

    def get(self, prompt_id: str) -> Job | None:
        return self._jobs.get(prompt_id)

    def all_jobs(self) -> tuple[Job, ...]:
        return tuple(self._jobs.values())

    def remove(self, prompt_id: str) -> Job | None:
        """Take the job out. The first caller gets it; every later one gets None."""
        job = self._jobs.pop(prompt_id, None)
        if job is None:
            return None
        self.release_ip(job.ip, prompt_id)
        return job

    def for_session(self, session_id: str) -> tuple[Job, ...]:
        return tuple(
            j for j in self._jobs.values() if j.submission.session_id == session_id
        )
