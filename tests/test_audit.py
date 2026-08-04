"""Append-only audit contract tests — FND-04: record/query surface, correlation trails, trigger tamper rejection."""

import asyncio
import uuid

import conftest
import pytest
import sqlalchemy
from sqlalchemy import func, select, text

from backend.database import AuditLog
from backend.services.audit import AuditService


async def _truncate(session) -> None:
    """Clear audit_logs between tests. TRUNCATE is allowed — the append-only
    trigger is a row-level BEFORE UPDATE OR DELETE, so it never fires here."""
    await session.execute(text("TRUNCATE audit_logs"))
    await session.commit()


def _client():
    """TestClient with the app imported AFTER fixtures set the test env."""
    from fastapi.testclient import TestClient

    from backend.main import app

    return TestClient(app, follow_redirects=False)


def _login(client):
    return client.post(
        "/auth/login",
        data={"email": "owner@test.local", "password": conftest.TEST_OWNER_PASSWORD},
    )


async def test_record_appends(migrated_db, test_session):
    """AuditService.record inserts exactly one row with the stored JSONB payload."""
    await _truncate(test_session)
    correlation_id = str(uuid.uuid4())
    entity_id = str(uuid.uuid4())
    await AuditService.record(
        test_session,
        actor="agent",
        action="proposal_created",
        entity_type="proposal",
        entity_id=entity_id,
        payload={"amount": "100.00"},
        correlation_id=correlation_id,
    )
    await test_session.commit()

    rows = (await test_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor == "agent"
    assert row.action == "proposal_created"
    assert row.entity_type == "proposal"
    assert row.entity_id == entity_id
    assert row.payload == {"amount": "100.00"}
    assert row.correlation_id == correlation_id


async def test_default_correlation_id_generated(migrated_db, test_session):
    """record() without correlation_id persists a non-empty uuid4 string."""
    await _truncate(test_session)
    await AuditService.record(
        test_session,
        actor="agent",
        action="lead_found",
        entity_type="lead",
        entity_id=str(uuid.uuid4()),
        payload={},
    )
    await test_session.commit()

    row = (await test_session.execute(select(AuditLog))).scalars().one()
    assert row.correlation_id
    assert uuid.UUID(row.correlation_id)  # raises ValueError if not a uuid4 string


async def test_query_by_correlation_id(migrated_db, test_session):
    """query(correlation_id=...) returns exactly that trail, newest first."""
    await _truncate(test_session)
    shared = str(uuid.uuid4())
    trail = [
        ("lead_found", "lead"),
        ("proposal_created", "proposal"),
        ("contract_signed", "contract"),
    ]
    for action, entity_type in trail:
        await AuditService.record(
            test_session,
            actor="agent",
            action=action,
            entity_type=entity_type,
            entity_id=str(uuid.uuid4()),
            payload={},
            correlation_id=shared,
        )
        await test_session.commit()
        await asyncio.sleep(0.01)  # distinct created_at => deterministic newest-first

    other = str(uuid.uuid4())
    await AuditService.record(
        test_session,
        actor="agent",
        action="email_sent",
        entity_type="email",
        entity_id=str(uuid.uuid4()),
        payload={},
        correlation_id=other,
    )
    await test_session.commit()

    rows = await AuditService.query(test_session, correlation_id=shared)
    assert [row.action for row in rows] == ["contract_signed", "proposal_created", "lead_found"]
    assert all(row.correlation_id == shared for row in rows)

    assert await AuditService.query(test_session, correlation_id=str(uuid.uuid4())) == []


def test_no_update_or_delete_paths():
    """The service surface is exactly record/query/list_recent — no mutation paths."""
    public = {name for name in dir(AuditService) if not name.startswith("_")}
    assert public == {"record", "query", "list_recent"}


async def test_trigger_rejects_update(migrated_db, test_session):
    """Raw UPDATE on audit_logs is rejected by the DB trigger before any row changes."""
    await _truncate(test_session)
    await AuditService.record(
        test_session,
        actor="agent",
        action="proposal_created",
        entity_type="proposal",
        entity_id=str(uuid.uuid4()),
        payload={"amount": "100.00"},
        correlation_id=str(uuid.uuid4()),
    )
    await test_session.commit()
    row_id = (await test_session.execute(select(AuditLog.id))).scalar_one()

    with pytest.raises(sqlalchemy.exc.DBAPIError, match="append-only"):
        await test_session.execute(
            text("UPDATE audit_logs SET payload = '{\"tampered\": true}'::jsonb WHERE id = :id"),
            {"id": str(row_id)},
        )
    await test_session.rollback()


async def test_trigger_rejects_delete(migrated_db, test_session):
    """Raw DELETE on audit_logs is rejected by the DB trigger before any row is touched."""
    await _truncate(test_session)
    await AuditService.record(
        test_session,
        actor="agent",
        action="proposal_created",
        entity_type="proposal",
        entity_id=str(uuid.uuid4()),
        payload={"amount": "100.00"},
        correlation_id=str(uuid.uuid4()),
    )
    await test_session.commit()
    row_id = (await test_session.execute(select(AuditLog.id))).scalar_one()

    with pytest.raises(sqlalchemy.exc.DBAPIError, match="append-only"):
        await test_session.execute(
            text("DELETE FROM audit_logs WHERE id = :id"),
            {"id": str(row_id)},
        )
    await test_session.rollback()

    count = (await test_session.execute(select(func.count()).select_from(AuditLog))).scalar_one()
    assert count == 1


async def test_audit_page_filters_by_correlation_id(migrated_db, test_session):
    """GET /audit?correlation_id=<trail> renders exactly that trail; /audit renders the full log."""
    await _truncate(test_session)
    trail = str(uuid.uuid4())
    for action in ("lead_found", "proposal_created"):
        await AuditService.record(
            test_session,
            actor="agent",
            action=action,
            entity_type="proposal",
            entity_id=str(uuid.uuid4()),
            payload={},
            correlation_id=trail,
        )
    await AuditService.record(
        test_session,
        actor="agent",
        action="email_sent",
        entity_type="email",
        entity_id=str(uuid.uuid4()),
        payload={},
        correlation_id=str(uuid.uuid4()),
    )
    await test_session.commit()

    with _client() as client:
        assert _login(client).status_code == 302
        filtered = client.get(f"/audit?correlation_id={trail}")
        full = client.get("/audit")

    assert filtered.status_code == 200
    assert "lead_found" in filtered.text
    assert "proposal_created" in filtered.text
    assert "email_sent" not in filtered.text

    assert full.status_code == 200
    assert "email_sent" in full.text


async def test_audit_page_escapes_payload_html(migrated_db, test_session):
    """Payloads render HTML-escaped — stored <script> must never reach the browser raw."""
    await _truncate(test_session)
    await AuditService.record(
        test_session,
        actor="agent",
        action="proposal_created",
        entity_type="proposal",
        entity_id=str(uuid.uuid4()),
        payload={"note": "<script>alert('xss')</script>"},
        correlation_id=str(uuid.uuid4()),
    )
    await test_session.commit()

    with _client() as client:
        assert _login(client).status_code == 302
        response = client.get("/audit")

    assert response.status_code == 200
    assert "<script>" not in response.text
    assert "\\u003c" in response.text  # Jinja2 tojson escaped the payload


async def test_audit_page_never_renders_correlation_id(migrated_db, test_session):
    """The correlation ID is a secret-ish handle — it never appears in the rendered page."""
    await _truncate(test_session)
    trail = str(uuid.uuid4())
    await AuditService.record(
        test_session,
        actor="agent",
        action="proposal_created",
        entity_type="proposal",
        entity_id=str(uuid.uuid4()),
        payload={},
        correlation_id=trail,
    )
    await test_session.commit()

    with _client() as client:
        assert _login(client).status_code == 302
        response = client.get(f"/audit?correlation_id={trail}")

    assert response.status_code == 200
    assert "proposal_created" in response.text
    assert trail not in response.text


def test_audit_filter_without_session_redirects_to_login(migrated_db):
    with _client() as client:
        response = client.get("/audit?correlation_id=whatever")
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"
