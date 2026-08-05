"""HN "Who is hiring" adapter — live Algolia collection through the compliant door.

hn.algolia.com is a documented API host, so api_hosts grants the robots.txt
exemption (D-31: API terms govern it) while the per-domain token bucket still
throttles requests. normalize_hn_job_post lives in normalize.py (Task 06).
"""

from collections.abc import AsyncIterator

from backend.services.discovery.base import (
    ParseError,
    RejectReason,
    RunContext,
    SourceAdapter,
    SourceCandidate,
)
from backend.services.discovery.normalize import normalize_hn_job_post
from backend.services.discovery.sanitize import strip_html_to_text

SEARCH = (
    "https://hn.algolia.com/api/v1/search_by_date"
    "?tags=story&query=Ask%20HN%20Who%20is%20hiring&hitsPerPage=5"
)
ITEM = "https://hn.algolia.com/api/v1/items/{object_id}"


class HNAlgoliaSource(SourceAdapter):
    """Fetch the newest "Who is hiring?" thread and its top-level comments (job posts)."""

    source_id = "hn"
    display_name = "Hacker News"
    short_name = "HN"
    api_hosts = frozenset({"hn.algolia.com"})

    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        """Yield sanitized, normalized candidates; per-item failures count as rejections."""
        search = await ctx.client.fetch(SEARCH)
        ctx.stat.record_request()
        hits = search.json().get("hits") or []
        if not isinstance(hits, list):
            hits = []
        if not hits:
            return
        thread = hits[0]
        items = await ctx.client.fetch(ITEM.format(object_id=thread["objectID"]))
        ctx.stat.record_request()
        children = items.json().get("children") or []
        if not isinstance(children, list):
            children = []
        for child in children:
            ctx.stat.record_found()
            try:
                text = strip_html_to_text(child.get("text") or "")
                if len(text.split()) < 4:  # empty/deleted comments
                    raise ParseError(RejectReason.TOO_SHORT, item_id=child.get("id"))
                normalized = normalize_hn_job_post(text, child)
            except ParseError as exc:  # per-item rejection — counted, never a candidate
                ctx.stat.reject(exc.reason, item_id=exc.item_id)
                continue
            ctx.stat.record_parsed()
            yield SourceCandidate(
                source_id=self.source_id,
                source_item_id=f"hn:{child['id']}",
                raw={
                    "hn_id": child.get("id"),
                    "thread_id": thread["objectID"],
                    "author": child.get("author"),
                },
                text=text,
                normalized=normalized,
            )


_MOCK_POSTS = (
    ("Acme Web Studio", "Remote (Worldwide)", "https://acme-web-studio.example.com/jobs"),
    ("Globex", "Berlin", "https://globex.example.com/careers"),
)


class MockHN(HNAlgoliaSource):
    """Deterministic mock candidates for MOCK_MODE (D-23) — never touches the network."""

    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        for index, (name, location, website) in enumerate(_MOCK_POSTS, start=1):
            ctx.stat.record_found()
            ctx.stat.record_parsed()
            yield SourceCandidate(
                source_id=self.source_id,
                source_item_id=f"mock-hn:{index}",
                raw={"mock": True, "thread_id": "mock"},
                text=f"{name} | {location} | {website}",
                normalized={
                    "name": name,
                    "website": website,
                    "location": location,
                    "industry": None,
                },
            )
