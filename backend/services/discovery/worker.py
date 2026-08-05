"""Outbox worker for discovery runs (T07) — durable, serial, cancellable.

Polls outbox_events for topic "discovery.run" and executes runs one at a time
(max_instances=1 semantics): IN_PROGRESS → execute_run → DONE, or FAILED with
last_error. Cancellation propagates cleanly so the lifespan can shut the loop
down without leaking tasks (D-12: long jobs live here, never in the scheduler).
"""

import asyncio
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from backend import database
from backend.database import OutboxEvent, utc_now
from backend.services.discovery.runner import execute_run

_DISCOVERY_TOPIC = "discovery.run"
_POLL_INTERVAL_SECONDS = 5.0
_MAX_ERROR_LENGTH = 1000


async def discovery_worker(*, poll_interval: float = _POLL_INTERVAL_SECONDS) -> None:
    """Drain discovery.run outbox events serially until cancelled (D-12)."""
    while True:
        try:
            await _process_one()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — a bad iteration must never kill the loop
            logger.exception("discovery worker iteration failed")
        await asyncio.sleep(poll_interval)


async def _process_one() -> bool:
    """Handle at most one PENDING event; returns True when one was processed."""
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        result = await session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.topic == _DISCOVERY_TOPIC,
                OutboxEvent.status == "PENDING",
            )
            .order_by(OutboxEvent.created_at)
            .limit(1)
        )
        event = result.scalars().first()
        if event is None:
            return False
        event.status = "IN_PROGRESS"
        event.attempts += 1
        await session.commit()
        try:
            await execute_run(UUID(event.payload["run_id"]))
        except Exception as exc:  # noqa: BLE001 — any run failure lands as FAILED
            event.status = "FAILED"
            event.last_error = str(exc)[:_MAX_ERROR_LENGTH]
            event.processed_at = utc_now()
            await session.commit()
            logger.error("discovery event {} failed: {}", event.id, exc)
            return True
        event.status = "DONE"
        event.processed_at = utc_now()
        await session.commit()
        return True
