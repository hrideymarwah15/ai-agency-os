"""Yelp adapter — key-gated (requires_keys), disabled by default (D-21).

Terms flags (02-RESEARCH §Sources): Yelp data is licensed for display within
Yelp — caching beyond 24h and AI-training use are restricted; live collection
is a later milestone. This phase ships the mock adapter only.
"""

from collections.abc import AsyncIterator

from backend.services.discovery.base import (
    ParseError,
    RejectReason,
    RunContext,
    SourceAdapter,
    SourceCandidate,
)


class YelpSource(SourceAdapter):
    """Key-gated source — raises ParseError(DISABLED) until a key is configured."""

    source_id = "yelp"
    display_name = "Yelp"
    short_name = "Yelp"
    requires_keys = True

    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        """Disabled without an API key; live collection is a later milestone."""
        ctx.stat.reject(RejectReason.DISABLED)
        raise ParseError(RejectReason.DISABLED)
        yield  # pragma: no cover — keeps this an async generator; the raise fires first


class MockYelp(YelpSource):
    """Deterministic mock candidates for MOCK_MODE (D-23) — never touches the network."""

    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        ctx.stat.record_found()
        ctx.stat.record_parsed()
        yield SourceCandidate(
            source_id=self.source_id,
            source_item_id="mock-yelp:1",
            raw={"mock": True},
            text="Pasta Palace | Italian restaurant in New York, NY",
            normalized={
                "name": "Pasta Palace",
                "website": "https://pastapalace.example.com",
                "location": "New York, NY",
                "industry": "restaurants",
            },
        )
