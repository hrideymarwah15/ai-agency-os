"""Outbox worker tests — T07: serial drain, failure marking, clean cancellation."""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

import backend.database as db
from backend.database import Business, DiscoveryRun, OutboxEvent, RunStatus
from backend.services.discovery import runner as runner_module
from backend.services.discovery.worker import discovery_worker

_POLL = 0.01


async def _noop_enrich(business, *, client, website=None):
    """Keep worker tests off the network — enrichment is covered in T06/T07 run tests."""
    return {"success": True, "fields": {}}


@pytest.fixture
def db_maker(test_engine, monkeypatch):
    """Point database.async_session_maker at the test engine (approvals pattern)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db, "async_session_maker", maker)
    return maker


@pytest.fixture(autouse=True)
async def clean_outbox(discovery_db, test_session):
    """Worker tests own outbox_events: no leftovers from other tests.

    discovery_db only truncates discovery tables — the worker drains the shared
    outbox, so stale events from earlier tests would break the drain assertions.
    (audit_logs is append-only by design — left alone.)
    """
    from sqlalchemy import delete

    from backend.database import OutboxEvent

    await test_session.execute(delete(OutboxEvent))
    await test_session.commit()
    yield


@pytest.fixture
def offline_enrich(monkeypatch):
    """Replace runner.enrich_homepage with a no-op for the worker tests."""
    monkeypatch.setattr(runner_module, "enrich_homepage", _noop_enrich)


async def _seed_run_and_event(test_session, *, at: datetime) -> DiscoveryRun:
    run = DiscoveryRun(
        trigger_source="MANUAL", status=RunStatus.RUNNING, correlation_id=str(uuid4())
    )
    test_session.add(run)
    await test_session.flush()
    test_session.add(
        OutboxEvent(
            topic="discovery.run",
            payload={"run_id": str(run.id), "correlation_id": run.correlation_id},
            created_at=at,
        )
    )
    await test_session.commit()
    await test_session.refresh(run)
    return run


async def _events(test_session):
    # The worker commits through its own session — expire cached instances so
    # this SELECT re-reads statuses from the DB instead of the identity map.
    test_session.expire_all()
    result = await test_session.execute(select(OutboxEvent).order_by(OutboxEvent.created_at))
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


async def test_worker_drains_events_serially_in_order(
    migrated_db, discovery_db, db_maker, offline_enrich, test_session
):
    """Two queued events → both DONE, processed in created_at order."""
    now = datetime.now(UTC)
    run_a = await _seed_run_and_event(test_session, at=now)
    run_b = await _seed_run_and_event(test_session, at=now + timedelta(seconds=1))
    ids = [run_a.id, run_b.id]  # plain UUIDs — safe after expire_all() in _events

    task = asyncio.create_task(discovery_worker(poll_interval=_POLL))
    try:
        rows = await _wait_until(
            test_session, lambda rows: len(rows) == 2 and all(r.status == "DONE" for r in rows)
        )
    finally:
        task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert rows[0].payload["run_id"] == str(ids[0])
    assert rows[0].processed_at is not None
    assert rows[0].processed_at <= rows[1].processed_at
    for row in rows:
        assert row.attempts >= 1

    statuses = [
        (
            await test_session.execute(select(DiscoveryRun).where(DiscoveryRun.id == rid))
        ).scalar_one()
        for rid in ids
    ]
    assert [s.status for s in statuses] == [RunStatus.COMPLETED, RunStatus.COMPLETED]


async def test_execute_run_exception_marks_event_failed(
    migrated_db, discovery_db, db_maker, offline_enrich, test_session
):
    """A run that raises → the event lands FAILED with last_error set."""
    missing_run_id = uuid4()  # no DiscoveryRun row → execute_run raises RuntimeError
    test_session.add(
        OutboxEvent(
            topic="discovery.run",
            payload={"run_id": str(missing_run_id), "correlation_id": str(uuid4())},
        )
    )
    await test_session.commit()

    task = asyncio.create_task(discovery_worker(poll_interval=_POLL))
    try:
        await _wait_until(
            test_session,
            lambda rows: len(rows) == 1 and rows[0].status == "FAILED",
        )
    finally:
        task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    event = (await _events(test_session))[0]
    assert event.status == "FAILED"
    assert event.last_error is not None
    assert "not found" in event.last_error


async def test_worker_exits_cleanly_on_cancellation(
    migrated_db, discovery_db, db_maker, offline_enrich, test_session
):
    """Cancelling an idle worker propagates CancelledError (clean shutdown path)."""
    task = asyncio.create_task(discovery_worker(poll_interval=_POLL))
    await asyncio.sleep(0.05)  # let the loop idle at least once
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # No stray state: no events, no runs created by the worker itself.
    assert await _events(test_session) == []
    businesses = (await test_session.execute(select(Business))).scalars().all()
    assert businesses == []
