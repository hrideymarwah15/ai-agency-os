"""Reddit exclusion tests (LEAD-04) — fetch raises ParseError(BLOCKED), writes
one source_excluded audit (actor system), and NEVER issues a single request.
Exclusion means exclusion: no robots.txt probe, no 403 retry, no scrape-around.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from backend.database import AuditLog
from backend.services.discovery.base import (
    ParseError,
    RejectReason,
    RunContext,
    SourceStatCollector,
)
from backend.services.discovery.sources.reddit import RedditSource
from backend.tools.http_client import build_compliant_client


def _counting_handler(calls: list[str]):
    """Handler that records EVERY request path — any hit is a violation."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500, text="must never be requested")

    return handler


async def test_reddit_fetch_raises_blocked_with_zero_requests(
    migrated_db, discovery_db, mock_transport
) -> None:
    """The adapter raises ParseError(BLOCKED); zero requests ever reach reddit hosts."""
    calls: list[str] = []
    client = build_compliant_client(mock_transport(_counting_handler(calls)))
    stat = SourceStatCollector("reddit")
    correlation_id = f"corr-{uuid4().hex[:8]}"
    ctx = RunContext(
        run_id=uuid4(),
        correlation_id=correlation_id,
        client=client,
        session=discovery_db,
        stat=stat,
    )

    with pytest.raises(ParseError) as exc_info:
        async for _ in RedditSource().fetch_candidates(ctx):
            pass

    assert exc_info.value.reason is RejectReason.BLOCKED
    assert calls == []  # LEAD-04: exclusion, never scrape-around
    assert stat.rejected == 1
    assert stat.rejection_buckets[RejectReason.BLOCKED.value] == 1

    rows = (
        (
            await discovery_db.execute(
                select(AuditLog).where(
                    AuditLog.action == "source_excluded",
                    AuditLog.correlation_id == correlation_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].actor == "system"
    assert rows[0].entity_type == "discovery_source"
    assert rows[0].entity_id == "reddit"
