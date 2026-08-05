"""Reddit adapter — live-excluded (LEAD-04), never issues requests.

Exclusion evidence: reddit.com robots.txt disallows crawlers and public JSON
endpoints return 403 without an approved OAuth app (02-RESEARCH §Sources); the
official Data API remains backlog (LEAD-06). No scrape-around is ever attempted.
"""

from collections.abc import AsyncIterator

from backend.services.audit import AuditService
from backend.services.discovery.base import (
    ParseError,
    RejectReason,
    RunContext,
    SourceAdapter,
    SourceCandidate,
)


class RedditSource(SourceAdapter):
    """Excluded platform — fetch raises ParseError(BLOCKED) and audits source_excluded."""

    source_id = "reddit"
    display_name = "Reddit"
    short_name = "Reddit"

    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        """Never fetch: audit the exclusion, count the rejection, raise BLOCKED."""
        await AuditService.record(
            ctx.session,
            actor="system",
            action="source_excluded",
            entity_type="discovery_source",
            entity_id=self.source_id,
            payload={"reason": "lead04_platform_excluded"},
            correlation_id=ctx.correlation_id,
        )
        ctx.stat.reject(RejectReason.BLOCKED)
        raise ParseError(RejectReason.BLOCKED)
        yield  # pragma: no cover — keeps this an async generator; the raise fires first


class MockReddit(RedditSource):
    """Deterministic mock candidates for MOCK_MODE (D-23) — never touches the network."""

    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        ctx.stat.record_found()
        ctx.stat.record_parsed()
        yield SourceCandidate(
            source_id=self.source_id,
            source_item_id="mock-reddit:1",
            raw={"mock": True},
            text="r/smallbusiness | Owner at Acme Web Studio",
            normalized={
                "name": "Acme Web Studio",
                "website": None,
                "location": None,
                "industry": None,
            },
        )
