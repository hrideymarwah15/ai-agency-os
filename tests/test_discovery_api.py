"""Discovery API surface — owner-guarded trigger + pipeline-state page (T-03).

T-03 scope (02-PLAN Task 3): POST /discovery/run creates a DiscoveryRun
(trigger_source=MANUAL, RUNNING) + OutboxEvent(topic="discovery.run") + audit
row in ONE transaction, 302 + flash to /discovery; GET /discovery renders the
pipeline-state page (empty states, zero-sources banner, nav active state).
Authentication and Origin checks follow the approvals pattern (T-03-03).
"""

import json
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
        response = client.post(
            "/discovery/run", headers={"origin": "https://evil.example"}
        )

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

    events = (await discovery_db.execute(select(OutboxEvent))).scalars().all()
    assert len(events) == 1
    event = events[0]
    assert event.topic == "discovery.run"
    assert event.payload["run_id"] == str(run.id)
    assert event.payload["correlation_id"] == run.correlation_id

    audits = (
        await discovery_db.execute(
            select(AuditLog).where(AuditLog.action == "discovery_triggered")
        )
    ).scalars().all()
    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor == "owner"
    assert audit.entity_type == "discovery_run"
    assert audit.entity_id == str(run.id)
    assert audit.payload == {"trigger_source": "MANUAL"}
    assert audit.correlation_id == run.correlation_id


async def test_api_discovery_page_renders_empty_state(
    migrated_db, discovery_db, zero_sources
):
    """Logged-in GET /discovery: 200 with the runs empty state, zero-sources
    banner, Run discovery button, and the Discovery nav link active."""
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.get("/discovery")

    assert response.status_code == 200
    assert EMPTY_RUNS_COPY in response.text
    assert ZERO_SOURCES_COPY in response.text
    assert 'href="/discovery" class="nav-link nav-link--active">Discovery</a>' in (
        response.text
    )
    # The button is inside a POST form to the trigger route.
    assert 'action="/discovery/run"' in response.text
    assert "Run discovery" in response.text
