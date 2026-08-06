"""Outbox worker for website audits (T04) — durable, serial, cancellable.

Polls outbox_events for topic "audit.run" and executes audits one at a time
(max_instances=1 semantics): IN_PROGRESS → execute_audit → DONE, or FAILED
with last_error. Cancellation propagates cleanly so the lifespan can shut the
loop down without leaking tasks (D-12: long jobs live here, never in the
scheduler). The browser-gated default renderer is the production seam; tests
inject fakes that never touch a browser or the network.
"""

import asyncio
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from backend import database
from backend.database import OutboxEvent, utc_now
from backend.services.audits.runner import default_renderer, execute_audit

_AUDIT_TOPIC = "audit.run"
_POLL_INTERVAL_SECONDS = 5.0
_MAX_ERROR_LENGTH = 1000


async def audit_worker(*, poll_interval: float = _POLL_INTERVAL_SECONDS) -> None:
    """Drain audit.run outbox events serially until cancelled (D-12)."""
    while True:
        try:
            await _process_one()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — a bad iteration must never kill the loop
            logger.exception("audit worker iteration failed")
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
                OutboxEvent.topic == _AUDIT_TOPIC,
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
            await execute_audit(UUID(event.payload["audit_id"]), renderer=default_renderer)
        except Exception as exc:  # noqa: BLE001 — any audit failure lands as FAILED
            event.status = "FAILED"
            event.last_error = str(exc)[:_MAX_ERROR_LENGTH]
            event.processed_at = utc_now()
            await session.commit()
            logger.error("audit event {} failed: {}", event.id, exc)
            return True
        event.status = "DONE"
        event.processed_at = utc_now()
        await session.commit()
        return True
