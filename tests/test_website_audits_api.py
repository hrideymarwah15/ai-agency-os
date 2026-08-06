"""Website audits API — trigger, list, lead history, per-audit detail (T-03).

Covers the enqueue-only trigger (row + audit.run outbox event + audit log in one
transaction, Pattern 2), re-audit = new row (D-39), owner-guarding + Origin
check (T-03-03), and the three structured view models (T-03-01): list (leads
with audits), lead history (newest first, cap 10), per-audit detail (scores,
CWV+methodology labels, tech stack, broken links, gaps, older audits).
"""

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote
from uuid import uuid4

import conftest
import httpx
import pytest
from sqlalchemy import select

from backend.database import (
    AuditLog,
    AuditStatus,
    Business,
    OutboxEvent,
    WebsiteAudit,
)

TRIGGER_FLASH = "Audit queued."
NO_LEADS_COPY = "No leads yet"
ZERO_AUDITS_COPY = "No audits yet"
HISTORY_EMPTY_COPY = "No audits yet for this lead"


@pytest.fixture(autouse=True)
async def clean_tables(audit_db, discovery_db):
    """WebsiteAudit rows (audit_db) + businesses (discovery_db) cleaned per test."""
    yield


def _client():
    from fastapi.testclient import TestClient

    from backend.main import app

    return TestClient(app, follow_redirects=False)


def _login(client: httpx.Client):
    return client.post(
        "/auth/login",
        data={"email": "owner@test.local", "password": conftest.TEST_OWNER_PASSWORD},
    )


def _flash_message(response: httpx.Response) -> str:
    """Flash copy from the percent-encoded JSON flash cookie (RFC 6265 ASCII)."""
    import urllib.parse

    raw = response.cookies.get("flash") or ""
    if not raw:
        return ""
    try:
        data = json.loads(urllib.parse.unquote(raw))
    except (ValueError, TypeError):
        return urllib.parse.unquote(raw)
    return data.get("message", "") if isinstance(data, dict) else unquote(raw)


async def _seed_business(test_session, *, name: str = "Acme Web Studio") -> Business:
    business = Business(name=name, website_url="https://example.com/")
    test_session.add(business)
    await test_session.commit()
    await test_session.refresh(business)
    return business


async def _seed_audit(
    test_session,
    business: Business,
    *,
    status: AuditStatus = AuditStatus.COMPLETED,
    scores: tuple[int, int, int, int] = (90, 80, 70, 60),
    hours_ago: int = 1,
    finished: bool | None = None,
    last_error: str | None = None,
) -> WebsiteAudit:
    """Seed a WebsiteAudit row the way the runner would persist it."""
    started = datetime.now(UTC) - timedelta(hours=hours_ago)
    audit = WebsiteAudit(
        business_id=business.id,
        status=status,
        audit_version="1.0",
        performance_score=scores[0],
        accessibility_score=scores[1],
        seo_score=scores[2],
        mobile_score=scores[3],
        cwv={
            "ttfb_ms": 210,
            "lcp_ms": 1900 if status == AuditStatus.COMPLETED else None,
            "cls": 0.02 if status == AuditStatus.COMPLETED else None,
            "inp_ms": 145 if status == AuditStatus.COMPLETED else None,
            "methodology": {
                "measured_with": "playwright" if status == AuditStatus.COMPLETED else "static",
                "inp_estimation": "scripted_event_timing"
                if status == AuditStatus.COMPLETED
                else "not_assessed",
                "notes": []
                if status == AuditStatus.COMPLETED
                else ["Browser unavailable — rendered metrics not measured"],
            },
        },
        tech_stack=[{"name": "react", "confidence": 0.9}],
        cms={"name": "wordpress", "confidence": 0.95},
        hosting={"name": "cloudflare", "confidence": 0.9},
        analytics=[{"name": "ga4", "confidence": 0.8}],
        last_error=last_error,
        started_at=started,
        finished_at=started if finished or (finished is None and status == AuditStatus.COMPLETED) else None,
    )
    test_session.add(audit)
    await test_session.commit()
    await test_session.refresh(audit)
    return audit


# ---------------------------------------------------------------------------
# Auth + Origin gates (T-03-03)
# ---------------------------------------------------------------------------


async def test_api_trigger_requires_login(
    migrated_db, audit_db, discovery_db, test_session
):
    """Unauthenticated POST → login, nothing created."""
    business = await _seed_business(test_session)
    with _client() as client:
        response = client.post(f"/website-audits/lead/{business.id}/run")
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"
    assert (await test_session.execute(select(WebsiteAudit))).scalars().all() == []
    assert (await test_session.execute(select(OutboxEvent))).scalars().all() == []


async def test_api_list_requires_login(migrated_db, audit_db, discovery_db):
    with _client() as client:
        response = client.get("/website-audits")
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


async def test_api_trigger_rejects_cross_origin(
    migrated_db, audit_db, discovery_db, test_session
):
    """T-03-03 defense-in-depth: cross-origin POST → 403, nothing created."""
    business = await _seed_business(test_session)
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.post(
            f"/website-audits/lead/{business.id}/run",
            headers={"origin": "https://evil.example"},
        )
    assert response.status_code == 403
    assert (await test_session.execute(select(WebsiteAudit))).scalars().all() == []


async def test_api_trigger_unknown_lead_404(migrated_db, audit_db, discovery_db):
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.post(f"/website-audits/lead/{uuid4()}/run")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Trigger: enqueue-only, one transaction, re-audit = new row (D-39)
# ---------------------------------------------------------------------------


async def test_api_trigger_creates_audit_row_outbox_and_audit_log(
    migrated_db, audit_db, discovery_db, test_session
):
    """One transaction: RUNNING row + audit.run event + audit_triggered log."""
    business = await _seed_business(test_session)
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.post(f"/website-audits/lead/{business.id}/run")
        assert response.status_code == 302
        assert response.headers["location"] == f"/website-audits/lead/{business.id}"
        assert TRIGGER_FLASH in _flash_message(response)

    audits = (await test_session.execute(select(WebsiteAudit))).scalars().all()
    assert len(audits) == 1
    audit = audits[0]
    assert audit.business_id == business.id
    assert audit.status == AuditStatus.RUNNING
    assert audit.audit_version  # stamped at enqueue

    events = (await test_session.execute(select(OutboxEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].topic == "audit.run"
    assert events[0].payload == {"audit_id": str(audit.id)}

    logs = (await test_session.execute(select(AuditLog))).scalars().all()
    assert any(
        log.action == "audit_triggered"
        and log.entity_type == "website_audit"
        and log.entity_id == str(audit.id)
        for log in logs
    )


async def test_api_trigger_re_audit_creates_new_row(
    migrated_db, audit_db, discovery_db, test_session
):
    """Second trigger → SECOND row — history, never overwrite (D-39)."""
    business = await _seed_business(test_session)
    await _seed_audit(test_session, business)
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.post(f"/website-audits/lead/{business.id}/run")
        assert response.status_code == 302

    audits = (await test_session.execute(select(WebsiteAudit))).scalars().all()
    assert len(audits) == 2
    assert len({a.id for a in audits}) == 2


# ---------------------------------------------------------------------------
# GET /website-audits — lead list (leads with ≥1 audit, newest first, cap 20)
# ---------------------------------------------------------------------------


async def test_api_list_no_leads_empty_state(migrated_db, audit_db, discovery_db):
    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get("/website-audits")
    assert page.status_code == 200
    assert NO_LEADS_COPY in page.text
    assert "<table" not in page.text


async def test_api_list_leads_without_audits_empty_state(
    migrated_db, audit_db, discovery_db, test_session
):
    await _seed_business(test_session)
    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get("/website-audits")
    assert ZERO_AUDITS_COPY in page.text
    assert "<table" not in page.text


async def test_api_list_renders_lead_rows(
    migrated_db, audit_db, discovery_db, test_session
):
    """Row: business, website, last audited, overall, status, links, re-audit."""
    lead = await _seed_business(test_session, name="Acme Corp")
    audit = await _seed_audit(test_session, lead, scores=(90, 80, 70, 60))
    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get("/website-audits")

    assert page.status_code == 200
    assert "Acme Corp" in page.text
    assert "example.com" in page.text
    assert "Complete" in page.text
    # overall = round(mean(90,80,70,60)) = 75
    assert '"75"' in page.text
    assert f'href="/website-audits/lead/{lead.id}"' in page.text
    assert f'href="/website-audits/{audit.id}"' in page.text
    assert f'action="/website-audits/lead/{lead.id}/run"' in page.text
    assert 'href="/website-audits" class="nav-link nav-link--active">Audits</a>' in page.text


async def test_api_list_running_overall_dash(
    migrated_db, audit_db, discovery_db, test_session
):
    """RUNNING latest audit → 'In progress' + '—' overall (never guessed)."""
    lead = await _seed_business(test_session)
    await _seed_audit(test_session, lead, status=AuditStatus.RUNNING, finished_at=None)
    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get("/website-audits")
    assert "In progress" in page.text
    assert '"—"' in page.text


# ---------------------------------------------------------------------------
# GET /website-audits/lead/{business_id} — per-lead history
# ---------------------------------------------------------------------------


async def test_lead_page_empty_state_runs_action(
    migrated_db, audit_db, discovery_db, test_session
):
    """Zero audits → empty-state + 'Run audits' trigger label."""
    lead = await _seed_business(test_session)
    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get(f"/website-audits/lead/{lead.id}")

    assert page.status_code == 200
    assert HISTORY_EMPTY_COPY in page.text
    assert "Run audits" in page.text
    assert f'action="/website-audits/lead/{lead.id}/run"' in page.text


async def test_lead_history_lists_newest_first_with_labels(
    migrated_db, audit_db, discovery_db, test_session
):
    lead = await _seed_business(test_session)
    old = await _seed_audit(test_session, lead, scores=(50, 60, 40, 60), hours_ago=2)
    new = await _seed_audit(test_session, lead, scores=(90, 80, 70, 60), hours_ago=1)
    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get(f"/website-audits/lead/{lead.id}")

    assert page.status_code == 200
    assert page.text.index(f"/website-audits/{new.id}") < page.text.index(f"/website-audits/{old.id}")
    assert "Re-audit" in page.text
    assert '"75"' in page.text  # newest overall
    assert '"52"' in page.text  # round(mean(50,60,40,60))=52 — oldest overall


async def test_lead_history_unknown_lead_404(migrated_db, audit_db, discovery_db):
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.get(f"/website-audits/lead/{uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /website-audits/{audit_id} — per-audit detail
# ---------------------------------------------------------------------------


async def test_detail_requires_login(migrated_db, audit_db, discovery_db, test_session):
    lead = await _seed_business(test_session)
    audit = await _seed_audit(test_session, lead)
    with _client() as client:
        response = client.get(f"/website-audits/{audit.id}")
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


async def test_detail_unknown_audit_404(migrated_db, audit_db, discovery_db):
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.get(f"/website-audits/{uuid4()}")
    assert response.status_code == 404


async def test_detail_completed_renders_full_sections(
    migrated_db, audit_db, discovery_db, test_session
):
    """Completed audit: scores, CWV table + methodology labels, detections."""
    lead = await _seed_business(test_session)
    audit = await _seed_audit(
        test_session,
        lead,
        scores=(90, 80, 70, 100),
        last_error=None,
    )
    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get(f"/website-audits/{audit.id}")

    assert page.status_code == 200
    assert "Scores" in page.text
    for label, value in (
        ("Performance", 90),
        ("Accessibility", 80),
        ("SEO", 70),
        ("Mobile", 100),
    ):
        assert label in page.text
        assert f'>{value}<' in page.text
    assert "Rendered (Playwright)" in page.text

    # Core Web Vitals with value units + Measured methodology
    assert "Core Web Vitals" in page.text
    assert "1.9s" in page.text  # 1900ms LCP
    assert "145ms" in page.text  # INP
    assert "0.02" in page.text  # CLS
    assert "210ms" in page.text  # TTFB
    assert "Measured" in page.text

    # detections
    assert "Tech stack" in page.text and "react" in page.text
    assert "CMS" in page.text and "wordpress" in page.text
    assert "Hosting" in page.text and "cloudflare" in page.text
    assert "Analytics" in page.text and "ga4" in page.text

    # footer run id
    assert f"Audit {audit.id}" in page.text


async def test_detail_failed_renders_error_only(
    migrated_db, audit_db, discovery_db, test_session
):
    lead = await _seed_business(test_session)
    audit = await _seed_audit(
        test_session,
        lead,
        status=AuditStatus.FAILED,
        scores=(0, 0, 0, 0),
        last_error="homepage returned 500",
    )
    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get(f"/website-audits/{audit.id}")

    assert page.status_code == 200
    assert "Failed" in page.text
    assert "homepage returned 500" in page.text
    assert "Core Web Vitals" not in page.text
    assert "score-value" not in page.text


async def test_detail_running_shows_note_only(
    migrated_db, audit_db, discovery_db, test_session
):
    lead = await _seed_business(test_session)
    audit = await _seed_audit(test_session, lead, status=AuditStatus.RUNNING, finished_at=None)
    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get(f"/website-audits/{audit.id}")

    assert page.status_code == 200
    assert "In progress" in page.text
    assert "Core Web Vitals" not in page.text


async def test_detail_static_only_labels_estimates_as_not_assessed(
    migrated_db, audit_db, discovery_db, test_session
):
    """Static-only run: '—' CWV values + 'Not assessed' labels (D-34 honesty)."""
    lead = await _seed_business(test_session)
    audit = WebsiteAudit(
        business_id=lead.id,
        status=AuditStatus.COMPLETED,
        audit_version="1.0",
        performance_score=80,
        accessibility_score=70,
        seo_score=60,
        mobile_score=50,
        cwv={
            "ttfb_ms": 210,
            "lcp_ms": None,
            "cls": None,
            "inp_ms": None,
            "methodology": {
                "measured_with": "static",
                "inp_estimation": "not_assessed",
                "notes": ["Browser unavailable — rendered metrics not measured"],
            },
        },
        tech_stack=[],
        cms=None,
        hosting=None,
        analytics=[],
        started_at=datetime.now(UTC) - timedelta(hours=1),
        finished_at=datetime.now(UTC) - timedelta(hours=1),
    )
    test_session.add(audit)
    await test_session.commit()
    await test_session.refresh(audit)

    with _client() as client:
        assert _login(client).status_code == 302
        page = client.get(f"/website-audits/{audit.id}")

    assert page.status_code == 200
    assert "Static only" in page.text
    assert "Not assessed" in page.text