"""Heartbeat-monitored scheduler — FND-07/D-12: short jobs, staleness check, error alert.

Jobs are enqueue-only and short (D-12/Pitfall 8): max_instances=1, coalesce,
misfire_grace_time; failures surface through the EVENT_JOB_ERROR listener
instead of dying silently.
"""

from datetime import UTC, datetime, timedelta

from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent  # type: ignore[import-untyped]
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend import database
from backend.database import DiscoveryRun, OutboxEvent, RunStatus, SchedulerHeartbeat
from backend.services.approvals import expire_stale
from backend.services.budget import prune_spend_rows
from backend.workflows import get_ceo_review_graph

_HEARTBEAT_JOB_ID = "heartbeat"
_SPEND_RESET_JOB_ID = "spend-window-reset"
_APPROVAL_SWEEPER_JOB_ID = "approval-sweeper"
_DISCOVERY_JOB_ID = "discovery-daily"
_HEARTBEAT_INTERVAL_SECONDS = 30
_APPROVAL_SWEEPER_INTERVAL_SECONDS = 60


async def write_heartbeat(session: AsyncSession, *, job_name: str = "heartbeat") -> None:
    """Upsert a heartbeat row for job_name (idempotent — one row per job)."""
    now = datetime.now(UTC)
    stmt = (
        pg_insert(SchedulerHeartbeat)
        .values(job_name=job_name, last_beat_at=now)
        .on_conflict_do_update(index_elements=["job_name"], set_={"last_beat_at": now})
    )
    await session.execute(stmt)
    await session.commit()


async def check_heartbeat_staleness(
    session: AsyncSession,
    *,
    threshold_seconds: int = 120,
    job_names: tuple[str, ...] = (_HEARTBEAT_JOB_ID,),
) -> list[str]:
    """Return tracked job names whose last beat is older than the threshold.

    A missing heartbeat row counts as stale.
    """
    threshold = datetime.now(UTC) - timedelta(seconds=threshold_seconds)
    rows = (await session.execute(select(SchedulerHeartbeat))).scalars().all()
    fresh = {
        row.job_name
        for row in rows
        if row.last_beat_at is not None and row.last_beat_at > threshold
    }
    return [name for name in job_names if name not in fresh]


async def _heartbeat_job() -> None:
    """Upsert the heartbeat row (short, enqueue-only — D-12)."""
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        await write_heartbeat(session, job_name=_HEARTBEAT_JOB_ID)


async def _spend_reset_job() -> None:
    """Prune old spend counters at the daily window boundary (D-12)."""
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        await prune_spend_rows(session, retention_days=30)


async def _approval_sweeper_job() -> None:
    """D-09: auto-reject PENDING approvals past expires_at (explicit, audited).

    Each stale request resumes as a reject with reason "timeout" (T-03-06);
    the decision audit lands with actor="system".
    """
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    graph = await get_ceo_review_graph()
    async with session_maker() as session:
        await expire_stale(session, graph, datetime.now(UTC))


async def _discovery_daily_job() -> None:
    """D-12 enqueue-only daily discovery: create the run + outbox event atomically.

    The run row and its discovery.run outbox event commit together; the worker
    (never this job) executes the pipeline (RESEARCH Pattern 2).
    """
    from uuid import uuid4

    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        run = DiscoveryRun(
            trigger_source="SCHEDULER",
            status=RunStatus.RUNNING,
            correlation_id=str(uuid4()),
        )
        session.add(run)
        await session.flush()
        session.add(
            OutboxEvent(
                topic="discovery.run",
                payload={"run_id": str(run.id), "correlation_id": run.correlation_id},
            )
        )
        await session.commit()


def _on_job_error(event: JobExecutionEvent) -> None:
    """D-12 silent-failure alert: any job exception reaches loguru."""
    logger.error(f"[scheduler] job failed: {event.job_id} — {event.exception!r}")


def build_scheduler() -> AsyncIOScheduler:
    """Build the app scheduler: heartbeat + spend-window-reset jobs, error alert."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _heartbeat_job,
        IntervalTrigger(seconds=_HEARTBEAT_INTERVAL_SECONDS),
        id=_HEARTBEAT_JOB_ID,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        _spend_reset_job,
        CronTrigger(hour=0),
        id=_SPEND_RESET_JOB_ID,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        _approval_sweeper_job,
        IntervalTrigger(seconds=_APPROVAL_SWEEPER_INTERVAL_SECONDS),
        id=_APPROVAL_SWEEPER_JOB_ID,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        _discovery_daily_job,
        CronTrigger(hour=0),
        id=_DISCOVERY_JOB_ID,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
    return scheduler


def start_scheduler() -> AsyncIOScheduler:
    """Build and start the scheduler; the caller keeps the instance for shutdown."""
    scheduler = build_scheduler()
    scheduler.start()
    return scheduler
