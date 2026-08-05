"""Mock directory source — deterministic fixture-shaped candidates (MOCK_MODE-safe).

The only mock-only source: SOURCE_MOCK_DIRECTORY_ENABLED gates it, and it is
disabled by default (D-21). Usable in both modes for demo/dry runs.
"""

from collections.abc import AsyncIterator

from backend.services.discovery.base import (
    RunContext,
    SourceAdapter,
    SourceCandidate,
)

_MOCK_ENTRIES = (
    ("Nimbus Labs", "San Francisco, CA", "https://nimbus.example.com"),
    ("Copperline Co", "Toronto, ON", "https://copperline.example.com"),
)


class MockDirectorySource(SourceAdapter):
    """Deterministic mock candidates from fixture-shaped data — never touches the network."""

    source_id = "mock_directory"
    display_name = "Mock Directory"
    short_name = "Mock"

    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        for index, (name, location, website) in enumerate(_MOCK_ENTRIES, start=1):
            ctx.stat.record_found()
            ctx.stat.record_parsed()
            yield SourceCandidate(
                source_id=self.source_id,
                source_item_id=f"mock-directory:{index}",
                raw={"mock": True},
                text=f"{name} | {location} | {website}",
                normalized={
                    "name": name,
                    "website": website,
                    "location": location,
                    "industry": None,
                },
            )
