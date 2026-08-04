"""Heartbeat-monitored scheduler tests — FND-07/D-12: heartbeat upsert, staleness, job-error alert."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from apscheduler.triggers.date import DateTrigger
from loguru import logger as loguru_logger
from sqlalchemy import delete, select

from backend.database import SchedulerHeartbeat
from backend.services.scheduler import build_scheduler, check_heartbeat_staleness, write_heartbeat


@pytest.fixture(autouse=True)
async def clean_heartbeats(test_session):
    """Every scheduler test starts from an empty scheduler_heartbeats table."""
    await test_session.execute(delete(SchedulerHeartbeat))
    await test_session.commit()
    yield


@pytest.fixture
def loguru_sink():
    """Capture loguru records for the duration of the test."""
    records: list[dict] = []
    sink_id = loguru_logger.add(records.append, format="{message}")
    yield records
    loguru_logger.remove(sink_id)


async def test_write_heartbeat_upserts_single_row(test_session):
    await write_heartbeat(test_session, job_name="heartbeat")
    await write_heartbeat(test_session, job_name="heartbeat")

    rows = (await test_session.execute(select(SchedulerHeartbeat))).scalars().all()
    assert len(rows) == 1
    assert rows[0].job_name == "heartbeat"
    assert rows[0].last_beat_at.tzinfo is not None


async def test_check_heartbeat_staleness_empty_when_fresh(test_session):
    await write_heartbeat(test_session, job_name="heartbeat")
    assert await check_heartbeat_staleness(test_session, threshold_seconds=120) == []


async def test_check_heartbeat_staleness_detects_old_beat(test_session):
    await write_heartbeat(test_session, job_name="heartbeat")
    row = (await test_session.execute(select(SchedulerHeartbeat))).scalar_one()
    row.last_beat_at = datetime.now(UTC) - timedelta(minutes=5)
    await test_session.commit()

    stale = await check_heartbeat_staleness(test_session, threshold_seconds=120)
    assert "heartbeat" in stale


async def test_check_heartbeat_staleness_missing_row_counts_stale(test_session):
    stale = await check_heartbeat_staleness(test_session, threshold_seconds=120)
    assert "heartbeat" in stale


async def test_job_error_listener_logs_via_loguru(loguru_sink, monkeypatch):
    """A job that raises fires EVENT_JOB_ERROR → loguru alert (D-12 silent-failure alert)."""

    async def _raise_job() -> None:
        raise RuntimeError("boom")

    # _raise_job must look like a plain function to apscheduler's job store.
    async def raising_job() -> None:
        await _raise_job()

    scheduler = build_scheduler()
    scheduler.add_job(
        raising_job,
        trigger=DateTrigger(run_date=datetime.now(UTC) + timedelta(milliseconds=100)),
        id="boom-job",
    )
    scheduler.start()
    await asyncio.sleep(0.6)
    scheduler.shutdown(wait=False)

    messages = [record["message"] for record in loguru_sink.records]
    assert any("[scheduler] job failed" in message for message in messages)
