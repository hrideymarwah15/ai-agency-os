"""Audit outbox worker tests — T04: serial drain, FAILED marking, clean cancellation.

Mirrors the discovery worker suite: the audit.run topic drains one event at a
time; failures land as event FAILED with last_error; idle loops cancel cleanly.
execute_audit is replaced with a fake that marks the audit COMPLETED so worker
tests never touch the network (runner behavior is covered in test_audit_runner).
"""

import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

import backend.database as db
from backend.database import AuditStatus, Business, OutboxEvent, WebsiteAudit
from backend.services.audits import worker as worker_module
from backend.services.audits.worker import audit_worker

_POLL = 0.01


async def _fake_execute(audit_id, *, client_factory=None, renderer=None):
    """Mark the audit row COMPLETED — proves the worker routed the payload id."""
    maker = db.async_session_maker
    async with maker() as session:
        audit = await session.get(WebsiteAudit, audit_id)
        audit.status = AuditStatus.COMPLETED
        audit.finished_at = datetime.now(UTC)
        await session.commit()


async def _fail_execute(audit_id, *, client_factory=None, renderer=None):
    raise RuntimeError("renderer crashed")


@pytest.fixture
def db_maker(test_engine, monkeypatch):
    """Point database.async_session_maker at the test engine (approvals pattern)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db, "async_session_maker", maker)
    return maker


@pytest.fixture(autouse=True)
async def clean_audit_worker_tables(audit_db, discovery_db, test_session):
    """Worker tests own audit rows, businesses, and the shared outbox."""
    from sqlalchemy import delete

    await test_session.execute(delete(OutboxEvent))
    await test_session.commit()
    yield


@pytest.fixture
def offline_execute(monkeypatch):
    """Replace worker.execute_audit with a no-network fake (run tests cover it)."""
    monkeypatch.setattr(worker_module, "execute_audit", _fake_execute)


async def _seed_audit_and_event(
    test_session, *, at: datetime | None = None
) -> tuple[WebsiteAudit, OutboxEvent]:
    business = Business(name="Acme Web Studio", website_url="https://example.com/")
    test_session.add(business)
    await test_session.flush()
    audit = WebsiteAudit(
        business_id=business.id,
        status=AuditStatus.RUNNING,
        audit_version="1.0",
    )
    test_session.add(audit)
    await test_session.flush()
    event = OutboxEvent(
        topic="audit.run",
        payload={"audit_id": str(audit.id)},
        created_at=at or datetime.now(UTC),
    )
    test_session.add(event)
    await test_session.commit()
    await test_session.refresh(audit)
    await test_session.refresh(event)
    return audit, event


async def _events(test_session) -> list[OutboxEvent]:
    # The worker commits through its own session — re-read statuses from the DB.
    test_session.expire_all()
    result = await test_session.execute(
        select(OutboxEvent)
        .order_by(OutboxEvent.created_at)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


async def _wait_until(test_session, predicate, timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    rows: list = []
    while time.monotonic() < deadline:
        rows = await _events(test_session)
        if predicate(rows):
            return rows
        await asyncio.sleep(_POLL)
    raise AssertionError(
        f"condition not met within {timeout}s (events={[(r.status, r.last_error) for r in rows]!r})"
    )


async def test_worker_drains_audit_events_serially_in_order(
    migrated_db, audit_db, discovery_db, db_maker, offline_execute, test_session
):
    """Two queued audit events → both DONE, audits COMPLETED, FIFO order."""
    now = datetime.now(UTC)
    audit_a, _event_a = await _seed_audit_and_event(test_session, at=now)
    audit_b, _event_b = await _seed_audit_and_event(test_session, at=now + timedelta(seconds=1))
    ids = [audit_a.id, audit_b.id]  # plain UUIDs — safe after expire_all() in _events

    task = asyncio.create_task(audit_worker(poll_interval=_POLL))
    try:
        rows = await _wait_until(
            test_session, lambda rows: len(rows) == 2 and all(r.status == "DONE" for r in rows)
        )
    finally:
        task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert rows[0].payload["audit_id"] == str(ids[0])
    assert rows[0].processed_at is not None
    assert rows[0].processed_at <= rows[1].processed_at
    for row in rows:
        assert row.attempts >= 1

    # Worker routed the payload to the right audit rows.
    test_session.expire_all()
    audits = (
        (await test_session.execute(select(WebsiteAudit).execution_options(populate_existing=True)))
        .scalars()
        .all()
    )
    assert {str(a.id): a.status for a in audits} == {
        str(ids[0]): AuditStatus.COMPLETED,
        str(ids[1]): AuditStatus.COMPLETED,
    }


async def test_worker_failure_marks_event_failed_with_last_error(
    migrated_db, audit_db, discovery_db, db_maker, test_session, monkeypatch
):
    """execute_audit raising → event FAILED, last_error recorded, row untouched."""
    monkeypatch.setattr(worker_module, "execute_audit", _fail_execute)
    _audit, event = await _seed_audit_and_event(test_session)
    event_id = event.id  # plain UUID — safe after expire_all() in _events

    task = asyncio.create_task(audit_worker(poll_interval=_POLL))
    try:
        rows = await _wait_until(
            test_session, lambda rows: len(rows) == 1 and rows[0].status == "FAILED"
        )
    finally:
        task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert rows[0].id == event_id
    assert "renderer crashed" in rows[0].last_error
    assert rows[0].attempts >= 1

    test_session.expire_all()
    row = (await test_session.execute(select(WebsiteAudit))).scalar_one()
    assert row.status == AuditStatus.RUNNING  # runner never marked it


async def test_worker_cancels_cleanly_when_idle(
    migrated_db, audit_db, discovery_db, db_maker, offline_execute
):
    """No events → the loop waits; cancelling surfaces CancelledError (D-12)."""
    task = asyncio.create_task(audit_worker(poll_interval=_POLL))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
