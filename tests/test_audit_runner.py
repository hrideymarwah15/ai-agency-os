"""Audit runner tests — T04: execute_audit end-to-end invariants (AUDT-01..03).

Covers the one-commit-at-completion invariant (Pitfall 5), static-mode scores on
a clean fixture, rendered-mode CWV merge with D-34 methodology labels, the
robots-denied FAILED path (D-32 door gate), broken-link status recording with
the AUDIT_EXTERNAL_LINK_CAP throttle (AUDT-03), and run-granularity auditing
(never one audit log per broken link). Every fetch flows through the
MockTransport fast-client factory — nothing touches the real internet.
"""

import gzip
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from backend.config import settings
from backend.database import AuditLog, AuditStatus, Business, WebsiteAudit
from backend.services.audits.runner import execute_audit
from backend.services.compliance.rate_limit import DomainTokenBucket
from backend.services.compliance.robots import RobotsPolicy
from backend.tools.http_client import CompliantHTTPClient

# Clean fixture: every rubric signal present, https, gzip-encoded, robots+sitemap
# reachable — static-mode audit should score 100 across all four dimensions.
_CLEAN_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Acme Web Studio, Expert Websites</title>
<meta name="description" content="Acme builds fast websites for small businesses.">
<meta property="og:title" content="Acme Web Studio">
<meta property="og:image" content="https://example.com/og.png">
<meta name="twitter:card" content="summary">
<link rel="canonical" href="https://example.com/">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Organization"}</script>
</head>
<body>
<h1>Acme Web Studio</h1>
<p>We build fast websites for small businesses.</p>
<img src="/assets/logo.png" alt="Acme logo">
<a href="https://example.com/about">About us</a>
<a href="https://example.com/broken">Broken page</a>
<a href="https://example.com/quote">Get a quote</a>
<a href="https://external.example.com/tools">Get a quote</a>
<a href="mailto:hello@acme.example.com">Email us</a>
<a href="tel:+14155550132">Call us</a>
<form action="/contact" method="post"><input name="q" aria-label="Search"></form>
</body>
</html>"""


def _make_handler(
    html: str = _CLEAN_HTML,
    *,
    robots: str = "User-agent: *\nAllow: /\n",
) -> Callable[[httpx.Request], httpx.Response]:
    """Return the MockTransport handler function serving the fixture site."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=robots)
        if path == "/sitemap.xml":
            return httpx.Response(200, text="<urlset/>")
        if path == "/broken":
            return httpx.Response(404, text="not found")
        if path == "/":
            return httpx.Response(
                200,
                content=gzip.compress(html.encode("utf-8")),
                headers={
                    "content-encoding": "gzip",
                    "content-type": "text/html; charset=utf-8",
                },
            )
        return httpx.Response(200, text="ok")

    return handler


@pytest.fixture
def fast_client_factory():
    """Compliant client over MockTransport with an instant-refill bucket."""
    inner = httpx.AsyncClient(transport=httpx.MockTransport(_make_handler()), timeout=10.0)

    def factory() -> CompliantHTTPClient:
        return CompliantHTTPClient(
            inner,
            bucket=DomainTokenBucket(capacity=1000.0, refill_per_sec=1000.0),
            policy=RobotsPolicy(inner, user_agent="test-agent", ttl_seconds=60),
        )

    return factory


@pytest.fixture
def db_maker(test_engine, monkeypatch):
    """Point database.async_session_maker at the test engine (approvals pattern)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    import backend.database as db

    maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db, "async_session_maker", maker)
    return maker


async def _seed_audit(test_session, *, website: str = "https://example.com/") -> WebsiteAudit:
    business = Business(name="Acme Web Studio", website_url=website)
    test_session.add(business)
    await test_session.flush()
    audit = WebsiteAudit(
        business_id=business.id,
        status=AuditStatus.RUNNING,
        audit_version=settings.audit_version,
    )
    test_session.add(audit)
    await test_session.commit()
    await test_session.refresh(audit)
    return audit


async def _audit_events(test_session, audit_id: str) -> list[AuditLog]:
    result = await test_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "website_audit", AuditLog.entity_id == audit_id
        )
    )
    return list(result.scalars().all())


async def test_clean_static_audit_scores_100(
    migrated_db, discovery_db, audit_db, db_maker, fast_client_factory, test_session
):
    """Clean fixture → all four rubrics 100, one commit, run-granularity audits."""
    audit = await _seed_audit(test_session)
    await execute_audit(audit.id, client_factory=fast_client_factory)
    test_session.expire_all()

    row = (await test_session.execute(select(WebsiteAudit))).scalar_one()
    assert row.id == audit.id
    assert row.status == AuditStatus.COMPLETED
    assert row.performance_score == 100
    assert row.accessibility_score == 100
    assert row.seo_score == 100
    assert row.mobile_score == 100
    assert row.audit_version == settings.audit_version
    assert row.finished_at is not None

    cwv = row.cwv
    assert cwv["ttfb_ms"] is not None
    assert cwv["methodology"]["measured_with"] == "static"
    assert cwv["lcp_ms"] is None  # static mode never guesses (D-34)
    assert row.gaps == []
    assert row.tech_stack == []
    assert row.cms is None
    assert row.hosting is None
    assert row.analytics == []
    assert row.raw_stats  # transparency: static signals stored for detail view

    actions = {e.action for e in await _audit_events(test_session, str(audit.id))}
    assert actions == {"audit_run_started", "audit_run_finished"}


async def test_rendered_mode_merges_cwv_with_methodology(
    migrated_db, discovery_db, audit_db, db_maker, fast_client_factory, test_session
):
    """Injected renderer: real CWV values + measured/estimation labels (D-34)."""
    audit = await _seed_audit(test_session)

    async def fake_renderer(url: str) -> dict:
        return {
            "lcp_ms": 2600.0,
            "cls": 0.05,
            "inp_ms": 250.0,
            "inp_source": "event",
        }

    await execute_audit(audit.id, client_factory=fast_client_factory, renderer=fake_renderer)
    test_session.expire_all()

    row = (await test_session.execute(select(WebsiteAudit))).scalar_one()
    assert row.status == AuditStatus.COMPLETED
    cwv = row.cwv
    assert cwv["lcp_ms"] == 2600.0
    assert cwv["inp_ms"] == 250.0
    assert cwv["methodology"]["measured_with"] == "playwright"
    assert cwv["methodology"]["inp_estimation"] == "scripted_event_timing"
    # LCP > 2500ms → −20; INP ≥ 200ms → −15 → 100 − 35 = 65.
    assert row.performance_score == 65


async def test_broken_links_recorded_with_statuses(
    migrated_db, discovery_db, audit_db, db_maker, fast_client_factory, test_session
):
    """Internal 404 + external OK + mailto/tel excluded (AUDT-03, D-37)."""
    audit = await _seed_audit(test_session)
    await execute_audit(audit.id, client_factory=fast_client_factory)
    test_session.expire_all()

    row = (await test_session.execute(select(WebsiteAudit))).scalar_one()
    by_url = {entry["url"]: entry for entry in row.broken_links}
    assert by_url["https://example.com/broken"]["status"] == "broken"
    assert by_url["https://example.com/broken"]["status_code"] == 404
    assert by_url["https://example.com/about"]["status"] == "ok"
    assert by_url["https://external.example.com/tools"]["status"] == "ok"
    # mailto/tel are not crackable links — never probed.
    assert not any("mailto:" in u or "tel:" in u for u in by_url)


async def test_external_link_cap_records_skipped(
    migrated_db, discovery_db, audit_db, db_maker, test_session
):
    """External links beyond AUDIT_EXTERNAL_LINK_CAP are recorded 'skipped' (D-37)."""
    external = "\n".join(f'<a href="https://external{i}.example.com/x">e{i}</a>' for i in range(8))
    html = _CLEAN_HTML.replace(
        '<a href="https://external.example.com/tools">Get a quote</a>', external
    )
    transport = httpx.MockTransport(_make_handler(html))
    inner = httpx.AsyncClient(transport=transport, timeout=10.0)

    def factory() -> CompliantHTTPClient:
        return CompliantHTTPClient(
            inner,
            bucket=DomainTokenBucket(capacity=1000.0, refill_per_sec=1000.0),
            policy=RobotsPolicy(inner, user_agent="test-agent", ttl_seconds=60),
        )

    audit = await _seed_audit(test_session)
    await execute_audit(audit.id, client_factory=factory)
    test_session.expire_all()

    row = (await test_session.execute(select(WebsiteAudit))).scalar_one()
    externals = [e for e in row.broken_links if "external" in e["url"]]
    checked = [e for e in externals if e["status"] != "skipped"]
    skipped = [e for e in externals if e["status"] == "skipped"]
    assert len(checked) == settings.audit_external_link_cap
    assert len(skipped) == 8 - settings.audit_external_link_cap


async def test_robots_denied_marks_failed(
    migrated_db, discovery_db, audit_db, db_maker, test_session
):
    """Deny-by-default: robots.txt denial → FAILED with audit_blocked event (D-32)."""
    transport = httpx.MockTransport(_make_handler(robots="User-agent: *\nDisallow: /\n"))
    inner = httpx.AsyncClient(transport=transport, timeout=10.0)

    def factory() -> CompliantHTTPClient:
        return CompliantHTTPClient(
            inner,
            bucket=DomainTokenBucket(capacity=1000.0, refill_per_sec=1000.0),
            policy=RobotsPolicy(inner, user_agent="test-agent", ttl_seconds=60),
        )

    audit = await _seed_audit(test_session)
    await execute_audit(audit.id, client_factory=factory)
    test_session.expire_all()

    row = (await test_session.execute(select(WebsiteAudit))).scalar_one()
    assert row.status == AuditStatus.FAILED
    assert row.last_error
    assert "robots" in row.last_error.lower()

    actions = {e.action for e in await _audit_events(test_session, str(audit.id))}
    assert "audit_blocked" in actions
    assert "audit_run_finished" in actions


async def test_missing_audit_raises(
    migrated_db, discovery_db, audit_db, db_maker, fast_client_factory
):
    """Unknown audit id → RuntimeError (worker marks the event FAILED)."""
    with pytest.raises(RuntimeError):
        await execute_audit(uuid4(), client_factory=fast_client_factory)
