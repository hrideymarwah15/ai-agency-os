"""Runner integration tests — T07: execute_run end-to-end invariants.

Covers the same-transaction stat invariants (Pitfall 5), PARTIAL semantics on a
429 (Pitfall 4 — never retry harder), disabled-source stats, the max-items cap,
and run-granularity-only auditing. Every fetch flows through the MockTransport
fast-client factory — nothing touches the real internet.
"""

import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

import backend.database as db
from backend.config import settings
from backend.database import (
    AuditLog,
    Business,
    BusinessSourceRecord,
    DiscoveryRun,
    DiscoveryRunSourceStat,
    RunStatus,
    SourceRunStatus,
)
from backend.services.compliance.rate_limit import DomainTokenBucket
from backend.services.compliance.robots import RobotsPolicy
from backend.services.discovery import registry
from backend.services.discovery.base import RejectReason, SourceAdapter, SourceCandidate
from backend.services.discovery.runner import execute_run
from backend.tools.http_client import CompliantHTTPClient

_HOMEPAGE_HTML = """<!doctype html><html><body>
<h1>Acme Web Studio</h1>
<p>We build websites for small businesses.</p>
<a href="mailto:hello@acme-web-studio.example.com">Email us</a>
<p>Call us at 415-555-0132</p>
<form action="/contact"><input name="name"></form>
</body></html>"""


def _homepage_handler(request: httpx.Request) -> httpx.Response:
    """Serve an allow-all robots.txt and the fixture homepage to any host."""
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")
    return httpx.Response(200, text=_HOMEPAGE_HTML)


@pytest.fixture
def db_maker(test_engine, monkeypatch):
    """Point database.async_session_maker at the test engine (approvals pattern)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db, "async_session_maker", maker)
    return maker


@pytest.fixture
def fast_client_factory():
    """Compliant client over the MockTransport with an instant-refill bucket."""

    def factory(adapter: SourceAdapter) -> CompliantHTTPClient:
        inner = httpx.AsyncClient(transport=httpx.MockTransport(_homepage_handler), timeout=10.0)
        return CompliantHTTPClient(
            inner,
            bucket=DomainTokenBucket(capacity=1000.0, refill_per_sec=1000.0),
            policy=RobotsPolicy(
                inner, user_agent="test-agent", ttl_seconds=60, api_hosts=adapter.api_hosts
            ),
        )

    return factory


async def _seed_run(test_session, trigger_source: str = "MANUAL") -> DiscoveryRun:
    run = DiscoveryRun(
        trigger_source=trigger_source, status=RunStatus.RUNNING, correlation_id=str(uuid4())
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)
    return run


async def _stats(test_session, run_id):
    result = await test_session.execute(
        select(DiscoveryRunSourceStat).where(DiscoveryRunSourceStat.run_id == run_id)
    )
    return {row.source_id: row for row in result.scalars().all()}


async def _audits(test_session, correlation_id: str):
    result = await test_session.execute(select(AuditLog).where(AuditLog.correlation_id == correlation_id))
    return list(result.scalars().all())


async def _run_row(test_session, run_id):
    result = await test_session.execute(select(DiscoveryRun).where(DiscoveryRun.id == run_id))
    return result.scalar_one()


async def test_manual_run_executes_with_same_tx_invariants(
    migrated_db, discovery_db, db_maker, fast_client_factory, test_session
):
    """End-to-end run: invariants hold without sleeps, audits stay run-granular."""
    run = await _seed_run(test_session)

    await execute_run(run.id, client_factory=fast_client_factory)
    await test_session.expire_all()

    run_row = await _run_row(test_session, run.id)
    assert run_row.status == RunStatus.COMPLETED
    assert run_row.finished_at is not None
    assert run_row.total_candidates == 2  # MockHN yields exactly 2 posts

    stats = await _stats(test_session, run.id)
    assert stats["hn"].status == SourceRunStatus.OK
    assert stats["hn"].found == stats["hn"].parsed_ok + stats["hn"].rejected
    assert stats["hn"].new_count + stats["hn"].merged_count == stats["hn"].parsed_ok
    for source_id in ("reddit", "yelp", "google_places", "mock_directory"):
        assert stats[source_id].status == SourceRunStatus.DISABLED

    lineage = (await test_session.execute(select(BusinessSourceRecord))).scalars().all()
    assert len(lineage) == 2

    audits = await _audits(test_session, run.correlation_id)
    assert {a.action for a in audits} == {"discovery_run_started", "run_finished"}
    finished = next(a for a in audits if a.action == "run_finished")
    assert finished.payload["total_candidates"] == 2
    assert finished.payload["status"] == "COMPLETED"

    # Enrichment ran inside the run: mock candidates carry no email, the
    # fixture homepage does — fill-if-missing must have set it (FR-062).
    businesses = (await test_session.execute(select(Business))).scalars().all()
    assert len(businesses) == 2
    assert any(b.email == "hello@acme-web-studio.example.com" for b in businesses)


async def test_all_disabled_sources_yield_completed_run_with_disabled_stats(
    migrated_db, discovery_db, db_maker, fast_client_factory, test_session, monkeypatch
):
    """Nothing enabled → every source gets a DISABLED stat, run still COMPLETED."""
    entries = [
        (source_id, adapter_cls, False, display, short)
        for source_id, adapter_cls, _enabled, display, short in registry.all_sources()
    ]
    monkeypatch.setattr(registry, "all_sources", lambda: entries)
    run = await _seed_run(test_session)

    await execute_run(run.id, client_factory=fast_client_factory)
    await test_session.expire_all()

    stats = await _stats(test_session, run.id)
    assert len(stats) == 5
    assert all(stat.status == SourceRunStatus.DISABLED for stat in stats.values())
    run_row = await _run_row(test_session, run.id)
    assert run_row.status == RunStatus.COMPLETED
    assert run_row.total_candidates == 0


class _FlakySource(SourceAdapter):
    """Enabled test source that 429s on its first (only) request (Pitfall 4)."""

    source_id = "flaky"
    display_name = "Flaky"
    short_name = "flaky"
    api_hosts = frozenset({"flaky.example.com"})

    def fetch_candidates(self, ctx):  # noqa: ANN001 — RunContext shape from base
        ctx.stat.record_request()
        request = httpx.Request("GET", "https://flaky.example.com/api")
        raise httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=request,
            response=httpx.Response(429, request=request),
        )
        yield  # unreachable — keeps this an async generator (mypy shape)


async def test_429_source_yields_partial_run_and_exclusion_audit(
    migrated_db, discovery_db, db_maker, fast_client_factory, test_session, monkeypatch
):
    """A 429 on the first request → BLOCKED stat, source_excluded audit, PARTIAL run."""
    entries = list(registry.all_sources()) + [("flaky", _FlakySource, True, "Flaky", "flaky")]
    monkeypatch.setattr(registry, "all_sources", lambda: entries)
    run = await _seed_run(test_session)

    await execute_run(run.id, client_factory=fast_client_factory)
    await test_session.expire_all()

    run_row = await _run_row(test_session, run.id)
    assert run_row.status == RunStatus.PARTIAL

    stats = await _stats(test_session, run.id)
    assert stats["flaky"].status == SourceRunStatus.BLOCKED
    assert stats["flaky"].requests_made == 1  # the source stops after the 429
    assert stats["flaky"].rejected == 1
    assert stats["flaky"].rejection_buckets == {"blocked": 1}
    assert stats["hn"].status == SourceRunStatus.OK  # other sources still attempted

    audits = await _audits(test_session, run.correlation_id)
    assert {a.action for a in audits} == {"discovery_run_started", "source_excluded", "run_finished"}
    excluded = next(a for a in audits if a.action == "source_excluded")
    assert excluded.payload["source_id"] == "flaky"
    assert excluded.actor == "system"


async def test_max_items_per_source_cap_honored(
    migrated_db, discovery_db, db_maker, fast_client_factory, test_session, monkeypatch
):
    """Runner stops ingesting a source after discovery_max_items_per_source."""
    monkeypatch.setattr(settings, "discovery_max_items_per_source", 1)
    run = await _seed_run(test_session)

    await execute_run(run.id, client_factory=fast_client_factory)
    await test_session.expire_all()

    stats = await _stats(test_session, run.id)
    assert stats["hn"].new_count + stats["hn"].merged_count == 1
    run_row = await _run_row(test_session, run.id)
    assert run_row.total_candidates == 1
    assert run_row.status == RunStatus.COMPLETED


async def test_parse_error_source_records_rejection_bucket(
    migrated_db, discovery_db, db_maker, fast_client_factory, test_session, monkeypatch
):
    """ParseError during a source stream lands in the rejection bucket (LEAD-05)."""

    class _ParseErrorSource(SourceAdapter):
        source_id = "bad_source"
        display_name = "Bad"
        short_name = "bad"
        api_hosts = frozenset()

        def fetch_candidates(self, ctx):  # noqa: ANN001 — RunContext shape from base
            yield SourceCandidate(
                source_id=self.source_id,
                source_item_id="bad:1",
                raw={"mock": True},
                text="x",
                normalized={"name": None, "website": None},
            )
            ctx.stat.reject(RejectReason.TOO_SHORT, item_id="bad:1")

    entries = list(registry.all_sources()) + [
        ("bad_source", _ParseErrorSource, True, "Bad", "bad")
    ]
    monkeypatch.setattr(registry, "all_sources", lambda: entries)
    run = await _seed_run(test_session)

    await execute_run(run.id, client_factory=fast_client_factory)
    await test_session.expire_all()

    stats = await _stats(test_session, run.id)
    assert stats["bad_source"].rejected == 1
    assert stats["bad_source"].rejection_buckets == {"too_short": 1}
    run_row = await _run_row(test_session, run.id)
    assert run_row.status == RunStatus.COMPLETED  # per-item rejections don't fail the run
