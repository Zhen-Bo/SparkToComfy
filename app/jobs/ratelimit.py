"""Generation cap per source IP. Configured in the [rate_limit] table of config/app.toml."""

from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.jobs.config import RATE_LIMIT


class IpRateLimiter:
    def __init__(self) -> None:
        self.enabled = RATE_LIMIT.enabled
        self._rate = parse(
            f"{RATE_LIMIT.max_generations} per {RATE_LIMIT.window_minutes} minute"
        )
        self._limiter = MovingWindowRateLimiter(MemoryStorage())

    def allows(self, ip: str) -> bool:
        """Ask without recording. Returns False once the allowance is spent."""
        return not self.enabled or self._limiter.test(self._rate, ip)

    def record(self, ip: str) -> None:
        if self.enabled:
            self._limiter.hit(self._rate, ip)
