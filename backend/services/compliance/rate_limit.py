"""In-process per-domain async token bucket with jitter (CMP-02, D-13).

Redis is absent locally (Assumption A2) so the rate limiter lives in-process:
token math on a monotonic clock, one bucket per domain, and a uniform random
jitter on every wait so bursts never line up with target servers (CMP-02).
"""

import asyncio
import random
import time


class DomainTokenBucket:
    """Per-domain rate limiter: capacity + refill-per-second, jittered waits."""

    def __init__(self, capacity: float, refill_per_sec: float) -> None:
        self.capacity = capacity
        self.refill = refill_per_sec
        self.tokens: dict[str, float] = {}
        self.last: dict[str, float] = {}

    async def acquire(self, domain: str) -> None:
        """Wait for one token in the domain's bucket, then consume it."""
        now = time.monotonic()
        self.tokens[domain] = min(
            self.capacity,
            self.tokens.get(domain, self.capacity)
            + (now - self.last.get(domain, now)) * self.refill,
        )
        self.last[domain] = now
        if self.tokens[domain] < 1:
            if self.refill <= 0:
                await asyncio.Event().wait()  # no refill — the bucket never recovers
            wait = (1 - self.tokens[domain]) / self.refill
            await asyncio.sleep(wait + random.uniform(0, 1 / self.refill))  # jitter per CMP-02
            self.tokens[domain] = 0
        else:
            self.tokens[domain] -= 1
