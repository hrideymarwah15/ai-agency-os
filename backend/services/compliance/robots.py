"""Deny-by-default robots.txt policy with per-domain TTL cache (CMP-01, D-13).

robotparser is the D-13 lock (stdlib); reppy 0.4.14 is the documented hardening
path if real-world robots.txt breaks parsing — not needed now. Any fetch or
parse failure denies the fetch (T-05-05) and is audited when a session is
available.
"""

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.audit import AuditService


class RobotsPolicy:
    """Per-domain robots.txt policy: fetched once per domain, TTL-cached, deny-by-default."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        user_agent: str,
        ttl_seconds: int,
        session: AsyncSession | None = None,
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._ttl_seconds = ttl_seconds
        self._session = session
        # domain -> (cached_at, parser); parser is None when the fetch failed.
        self._cache: dict[str, tuple[float, RobotFileParser | None]] = {}

    async def can_fetch(self, url: str) -> bool:
        """True only when the (cached) robots.txt allows url for our user agent."""
        parsed = urlparse(url)
        host = parsed.hostname or ""
        now = time.monotonic()
        cached = self._cache.get(host)
        if cached is not None and now - cached[0] < self._ttl_seconds:
            parser = cached[1]
            if parser is None:
                return False
            return parser.can_fetch(self._user_agent, url)
        parser = await self._load(host, parsed.scheme)
        self._cache[host] = (now, parser)
        if parser is None:
            return False
        return parser.can_fetch(self._user_agent, url)

    async def _load(self, host: str, scheme: str) -> RobotFileParser | None:
        """Fetch and parse robots.txt for host; None on any failure (deny-by-default)."""
        try:
            response = await self._client.get(f"{scheme}://{host}/robots.txt")
            response.raise_for_status()
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            return parser
        except (httpx.HTTPError, OSError, ValueError):
            logger.warning(
                "robots.txt unavailable for {host} — denying by default", host=host, exc_info=True
            )
            await self._audit_default_deny(host)
            return None

    async def _audit_default_deny(self, host: str) -> None:
        """Record the default-deny decision (T-05-05) when a session is provided."""
        if self._session is None:
            return
        await AuditService.record(
            self._session,
            actor="system",
            action="robots_denied_by_default",
            entity_type="domain",
            entity_id=host,
            payload={"reason": "robots.txt fetch or parse failed"},
        )
        await self._session.commit()
