"""Discovery API surface — owner-guarded trigger + pipeline-state page (T-03).

T-03 scope (02-PLAN Task 3): POST /discovery/run creates a DiscoveryRun
(trigger_source=MANUAL, RUNNING) + OutboxEvent(topic="discovery.run") + audit
row in ONE transaction, 302 + flash to /discovery; GET /discovery renders the
pipeline-state page (empty states, zero-sources banner, nav active state).
Authentication and Origin checks follow the approvals pattern (T-03-03).
"""

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote

import conftest
import httpx
import pytest
from sqlalchemy import select

from backend.database import AuditLog, DiscoveryRun, OutboxEvent, RunStatus

TRIGGER_FLASH = "Discovery run queued."
ZERO_SOURCES_COPY = "No discovery sources are enabled"
EMPTY_RUNS_COPY = "No discovery runs yet"


@pytest.fixture
def zero_sources(monkeypatch):
    """Disable every discovery source flag so the zero-sources banner renders.

    Defaults enable HN (config lock test); this fixture flips the live settings
    singleton (the object backend.api.discovery reads) like hermetic_llm does.
    """
    import backend.config as config_module

    for name in (
        "source_hn_enabled",
        "source_reddit_enabled",
        "source_yelp_enabled",
        "source_google_places_enabled",
        "source_mock_directory_enabled",
    ):
        monkeypatch.setattr(config_module.settings, name, False)


def _client():
    """TestClient with the app imported after the conftest test env is fixed."""
    from fastapi.testclient import TestClient

    from backend.main import app

    return TestClient(app, follow_redirects=False)


def _login(client):
    return client.post(
        "/auth/login",
        data={"email": "owner@test.local", "password": conftest.TEST_OWNER_PASSWORD},
    )


def _flash_message(response: httpx.Response) -> str:
    """Flash copy from the percent-encoded JSON flash cookie (RFC 6265 ASCII)."""
    raw = response.cookies.get("flash") or ""
    if not raw:
        return ""
    try:
        data = json.loads(unquote(raw))
    except ValueError:
        return unquote(raw)
    return data.get("message", "") if isinstance(data, dict) else raw


async def test_api_discovery_page_requires_login(migrated_db, discovery_db):
    """Unauthenticated GET /discovery bounces to the login page (T-01-03 rule)."""
    with _client() as client:
        response = client.get("/discovery")

    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


async def test_api_run_requires_login(migrated_db, discovery_db):
    """Unauthenticated POST /discovery/run is owner-guarded: 302 to login."""
    with _client() as client:
        response = client.post("/discovery/run")

    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"

    rows = (await discovery_db.execute(select(DiscoveryRun))).scalars().all()
    assert rows == []  # nothing was created


async def test_api_run_rejects_cross_origin(migrated_db, discovery_db):
    """T-03-03 defense-in-depth: a cross-origin mutating POST gets 403."""
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.post("/discovery/run", headers={"origin": "https://evil.example"})

    assert response.status_code == 403

    rows = (await discovery_db.execute(select(DiscoveryRun))).scalars().all()
    assert rows == []  # the trigger never ran


async def test_api_run_creates_run_outbox_audit(migrated_db, discovery_db):
    """Logged-in trigger: 302 + flash; exactly one DiscoveryRun (MANUAL/RUNNING,
    correlation_id set), one OutboxEvent(topic discovery.run, payload run_id +
    correlation_id), one discovery_triggered audit row — same transaction."""
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.post("/discovery/run")

        assert response.status_code == 302
        assert response.headers["location"] == "/discovery"
        assert TRIGGER_FLASH in _flash_message(response)

    runs = (await discovery_db.execute(select(DiscoveryRun))).scalars().all()
    assert len(runs) == 1
    run = runs[0]
    assert run.trigger_source == "MANUAL"
    assert run.status == RunStatus.RUNNING
    assert run.correlation_id and len(run.correlation_id) <= 64

    # Run-scoped assertions: the persistent test DB accumulates rows across
    # runs (audit_logs is append-only by DB trigger), so filter by the run's
    # own correlation_id / run_id — leftovers from earlier runs never match.
    events = [
        event
        for event in (await discovery_db.execute(select(OutboxEvent))).scalars().all()
        if event.topic == "discovery.run" and event.payload.get("run_id") == str(run.id)
    ]
    assert len(events) == 1
    event = events[0]
    assert event.topic == "discovery.run"
    assert event.payload["run_id"] == str(run.id)
    assert event.payload["correlation_id"] == run.correlation_id

    audits = (
        (
            await discovery_db.execute(
                select(AuditLog).where(
                    AuditLog.action == "discovery_triggered",
                    AuditLog.correlation_id == run.correlation_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor == "owner"
    assert audit.entity_type == "discovery_run"
    assert audit.entity_id == str(run.id)
    assert audit.payload == {"trigger_source": "MANUAL"}
    assert audit.correlation_id == run.correlation_id


async def test_api_discovery_page_renders_empty_state(migrated_db, discovery_db, zero_sources):
    """Logged-in GET /discovery: 200 with the runs empty state, zero-sources
    banner, Run discovery button, and the Discovery nav link active."""
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.get("/discovery")

    assert response.status_code == 200
    assert EMPTY_RUNS_COPY in response.text
    assert ZERO_SOURCES_COPY in response.text
    assert 'href="/discovery" class="nav-link nav-link--active">Discovery</a>' in (response.text)
    # The button is inside a POST form to the trigger route.
    assert 'action="/discovery/run"' in response.text
    assert "Run discovery" in response.text


async def _seed_dashboard(test_session):
    """One PARTIAL run (metrics, rejections, blocked/error rows), one RUNNING run, two leads."""
    from decimal import Decimal

    from backend.database import (
        Business,
        BusinessSourceRecord,
        DiscoveryRun,
        DiscoveryRunSourceStat,
        RunStatus,
        SourceRunStatus,
    )

    started_a = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
    run_a = DiscoveryRun(
        trigger_source="MANUAL",
        status=RunStatus.PARTIAL,
        correlation_id="corr-t09-a",
        started_at=started_a,
        finished_at=started_a + timedelta(seconds=45),
    )
    run_b = DiscoveryRun(
        trigger_source="SCHEDULER",
        status=RunStatus.RUNNING,
        correlation_id="corr-t09-b",
        started_at=datetime(2026, 8, 5, 11, 0, tzinfo=UTC),
    )
    test_session.add_all([run_a, run_b])
    await test_session.flush()
    test_session.add_all(
        [
            DiscoveryRunSourceStat(
                run_id=run_a.id,
                source_id="hn",
                status=SourceRunStatus.OK,
                requests_made=21,
                found=21,
                parsed_ok=15,
                rejected=6,
                new_count=10,
                merged_count=5,
                rejection_buckets={"missing_website": 4, "too_short": 2},
            ),
            DiscoveryRunSourceStat(
                run_id=run_a.id,
                source_id="reddit",
                status=SourceRunStatus.BLOCKED,
                requests_made=1,
                rejected=1,
                rejection_buckets={"blocked": 1},
            ),
            DiscoveryRunSourceStat(
                run_id=run_a.id, source_id="yelp", status=SourceRunStatus.DISABLED
            ),
            DiscoveryRunSourceStat(
                run_id=run_a.id,
                source_id="google_places",
                status=SourceRunStatus.ERROR,
                requests_made=3,
                found=3,
                parsed_ok=1,
                rejected=2,
                rejection_buckets={"malformed": 2},
            ),
            DiscoveryRunSourceStat(
                run_id=run_a.id, source_id="mock_directory", status=SourceRunStatus.DISABLED
            ),
            DiscoveryRunSourceStat(
                run_id=run_b.id,
                source_id="hn",
                status=SourceRunStatus.OK,
                found=2,
                parsed_ok=2,
                new_count=1,
                merged_count=1,
            ),
            DiscoveryRunSourceStat(
                run_id=run_b.id, source_id="reddit", status=SourceRunStatus.DISABLED
            ),
            DiscoveryRunSourceStat(
                run_id=run_b.id, source_id="yelp", status=SourceRunStatus.DISABLED
            ),
            DiscoveryRunSourceStat(
                run_id=run_b.id, source_id="google_places", status=SourceRunStatus.DISABLED
            ),
            DiscoveryRunSourceStat(
                run_id=run_b.id, source_id="mock_directory", status=SourceRunStatus.DISABLED
            ),
        ]
    )
    lead_a = Business(
        name="Acme Web Studio",
        industry="Web design",
        location="San Francisco",
        website_url="https://acme.example.com",
        email="hello@acme.example.com",
        phone="415-555-0132",
        tech_stack=["python", "fastapi"],
    )
    lead_b = Business(
        name="Globex Engineering",
        industry="Manufacturing",
        location="Oakland",
        website_url="https://globex.example.com",
        rating=Decimal("4.5"),
        employee_count=12,
        review_count=7,
    )
    test_session.add_all([lead_a, lead_b])
    await test_session.flush()
    test_session.add_all(
        [
            BusinessSourceRecord(
                business_id=lead_a.id,
                run_id=run_a.id,
                source_id="hn",
                source_item_id="mock-hn:1",
                raw_payload={"mock": True},
                sanitized_text="Acme Web Studio | San Francisco | https://acme.example.com",
                status="NEW",
            ),
            BusinessSourceRecord(
                business_id=lead_a.id,
                run_id=run_a.id,
                source_id="mock_directory",
                source_item_id="mock-dir:1",
                raw_payload={"mock": True},
                sanitized_text="Acme Web Studio",
                status="MERGED",
            ),
            BusinessSourceRecord(
                business_id=lead_b.id,
                run_id=run_b.id,
                source_id="hn",
                source_item_id="mock-hn:2",
                raw_payload={"mock": True},
                sanitized_text="Globex Engineering",
                status="NEW",
            ),
        ]
    )
    await test_session.commit()


async def test_api_discovery_page_renders_metrics_and_leads_async(
    migrated_db, discovery_db, test_session
):
    await _seed_dashboard(test_session)
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.get("/discovery")
    html = response.text

    # Per-source parsed/found cells: 12/15 (hn, run_a), 2/2 (hn, run_b), "—" for disabled.
    assert "15/21" in html  # hn parsed/found (12/15 was the wrong ratio)
    assert "2/2" in html
    assert '<td class="num">—</td>' in html

    # tfoot totals: source-level found + Σ New/Merged + dedup rate 35% (6/17).
    import re

    tfoot = re.search(r"<tfoot>.*?</tfoot>", html, re.DOTALL).group(0)
    assert "23" in tfoot  # hn found 21 + 2
    assert "11" in tfoot  # new 10 + 1
    assert "6" in tfoot  # merged 5 + 1
    assert "Dedup rate 35%" in tfoot

    # Duration: 45s for the finished run, "In progress" for the RUNNING one.
    assert "45s" in html
    assert "In progress" in html

    # Expander rejection line + blocked/error rows (LEAD-04 visible).
    assert "missing_website 4 · too_short 2" in html
    assert "Blocked" in html
    assert "Error" in html

    # Leads: structured fields, lineage badges in registry order, enrichment, found date.
    assert "Acme Web Studio" in html
    assert "Web design" in html
    assert "San Francisco" in html
    assert "Globex Engineering" in html
    assert "4.5" in html
    assert "7/10" in html
    assert "2026-08-05 10:00 UTC" in html
    assert html.index("Globex Engineering") < html.index("Acme Web Studio")  # newest first
    assert "HN" in html
    assert "Mock" in html  # second lineage badge for the two-source lead
    assert "Website" in html
    assert "hello@acme.example.com" in html  # detail-list email

    # Structured-only (T-03-01): no raw payload keys, no sanitized prose, no correlation ids.
    for token in (
        "raw_payload",
        "sanitized_text",
        "source_item_id",
        "mock-hn:1",
        "corr-t09",
        "| San Francisco |",
    ):
        assert token not in html


async def test_api_discovery_page_renders_dedup_dash_when_no_candidates(
    migrated_db, discovery_db, test_session
):
    """Zero candidates across runs → the totals dedup cell renders "—"."""
    import re

    from backend.database import (
        DiscoveryRun,
        DiscoveryRunSourceStat,
        RunStatus,
        SourceRunStatus,
    )

    run = DiscoveryRun(
        trigger_source="MANUAL",
        status=RunStatus.COMPLETED,
        correlation_id="corr-t09-c",
        started_at=datetime(2026, 8, 5, 9, 0, tzinfo=UTC),
        finished_at=datetime(2026, 8, 5, 9, 0, 30, tzinfo=UTC),
    )
    test_session.add(run)
    await test_session.flush()
    test_session.add(
        DiscoveryRunSourceStat(run_id=run.id, source_id="hn", status=SourceRunStatus.EMPTY)
    )
    await test_session.commit()

    with _client() as client:
        assert _login(client).status_code == 302
        response = client.get("/discovery")
    html = response.text

    assert "Dedup rate" not in html
    tfoot = re.search(r"<tfoot>.*?</tfoot>", html, re.DOTALL).group(0)
    assert '<td class="num">—</td>' in tfoot
