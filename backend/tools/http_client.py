"""The single compliant HTTP door (D-15 #1): robots check → rate limit → request.

No other module issues outbound GETs — Phase 2's crawler routes through
build_compliant_client(). A denied robots.txt raises RobotsDeniedError BEFORE
any request is issued (T-05-01), and per-domain throttling comes from the
shared token bucket (CMP-02).

D-31: documented-API hosts passed via api_hosts bypass robots.txt (API terms
govern them) but still flow through the per-domain token bucket. Default ∅
preserves Phase 1 deny-by-default behavior.
"""

from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.services.compliance.rate_limit import DomainTokenBucket
from backend.services.compliance.robots import RobotsPolicy


class RobotsDeniedError(RuntimeError):
    """Raised when robots.txt denies the fetch — the request is never issued."""


class CompliantHTTPClient:
    """Fetch pipeline enforcing robots.txt and per-domain rate limits on every request."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        bucket: DomainTokenBucket,
        policy: RobotsPolicy,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._policy = policy

    async def fetch(self, url: str) -> httpx.Response:
        """Fetch url iff robots allow it, throttled by the per-domain token bucket."""
        if not await self._policy.can_fetch(url):
            raise RobotsDeniedError(f"robots.txt denies fetching {url}")
        await self._bucket.acquire(urlparse(url).hostname or "")
        response = await self._client.get(url)
        response.raise_for_status()
        return response


_shared_bucket: DomainTokenBucket | None = None


def build_compliant_client(
    client: httpx.AsyncClient | None = None,
    *,
    session: AsyncSession | None = None,
    api_hosts: frozenset[str] = frozenset(),
) -> CompliantHTTPClient:
    """Wire settings into a CompliantHTTPClient sharing one bucket across factories.

    api_hosts (D-31) lists documented-API hosts exempt from robots.txt — the
    token bucket still applies to them. Default empty set = Phase 1 behavior.
    """
    global _shared_bucket
    inner = client if client is not None else httpx.AsyncClient(timeout=60.0)
    if _shared_bucket is None:
        _shared_bucket = DomainTokenBucket(
            capacity=settings.rate_limit_capacity,
            refill_per_sec=settings.rate_limit_refill_per_sec,
        )
    policy = RobotsPolicy(
        inner,
        user_agent=settings.crawler_user_agent,
        ttl_seconds=settings.robots_cache_ttl_seconds,
        session=session,
        api_hosts=api_hosts,
    )
    return CompliantHTTPClient(inner, bucket=_shared_bucket, policy=policy)
