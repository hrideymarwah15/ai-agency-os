"""Outbox worker for opportunity rescoring (audit.completed events).

Drains ``audit.completed`` events one at a time, calls :func:`rescore_lead`, and
marks the event DONE. Mirrors the pattern used by the discovery and audits
workers.
"""

import asyncio
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from backend import database
from backend.database import OutboxEvent, WebsiteAudit, utc_now

from .engine import rescore_lead

_OPPORTUNITY_TOPIC = "audit.completed"
_POLL_INTERVAL_SECONDS = 5.0
_MAX_ERROR_LENGTH = 1000


async def opportunity_worker(*, poll_interval: float = _POLL_INTERVAL_SECONDS) -> None:
    """Drain ``audit.completed`` events → rescore leads → upsert opportunities."""
    while True:
        try:
            await _process_one()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 – ensure loop continues on errors
            logger.exception("opportunity worker iteration failed")
        await asyncio.sleep(poll_interval)


async def _process_one() -> bool:
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        result = await session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.topic == _OPPORTUNITY_TOPIC,
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
            audit_id = event.payload.get("audit_id")
            # Resolve the business_id via the audit row
            audit = await session.get(WebsiteAudit, UUID(audit_id)) if audit_id else None
            business_id = audit.business_id if audit else None
            if business_id:
                await rescore_lead(session, business_id)
        except Exception as exc:  # noqa: BLE001
            event.status = "FAILED"
            event.last_error = str(exc)[:_MAX_ERROR_LENGTH]
            event.processed_at = utc_now()
            await session.commit()
            logger.error("opportunity event {} failed: {}", event.id, exc)
            return True
        event.status = "DONE"
        event.processed_at = utc_now()
        await session.commit()
        return True
