"""Google Places adapter — key-gated (requires_keys), disabled by default (D-21).

Terms flags (02-RESEARCH §Sources): Google Maps Platform ToS prohibit caching
Places data; live collection is a later milestone. This phase ships the mock
adapter only.
"""

from collections.abc import AsyncIterator

from backend.services.discovery.base import (
    ParseError,
    RejectReason,
    RunContext,
    SourceAdapter,
    SourceCandidate,
)


class GooglePlacesSource(SourceAdapter):
    """Key-gated source — raises ParseError(DISABLED) until a key is configured."""

    source_id = "google_places"
    display_name = "Google Places"
    short_name = "G Maps"
    requires_keys = True

    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        """Disabled without an API key; live collection is a later milestone."""
        ctx.stat.reject(RejectReason.DISABLED)
        raise ParseError(RejectReason.DISABLED)
        yield  # pragma: no cover — keeps this an async generator; the raise fires first


class MockGooglePlaces(GooglePlacesSource):
    """Deterministic mock candidates for MOCK_MODE (D-23) — never touches the network."""

    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        ctx.stat.record_found()
        ctx.stat.record_parsed()
        yield SourceCandidate(
            source_id=self.source_id,
            source_item_id="mock-google-places:1",
            raw={"mock": True},
            text="Bright Bytes | Web design agency in Austin, TX",
            normalized={
                "name": "Bright Bytes",
                "website": "https://brightbytes.example.com",
                "location": "Austin, TX",
                "industry": "web_design",
            },
        )
