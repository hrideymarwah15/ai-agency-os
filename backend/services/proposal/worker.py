"""Durable outbox worker for asynchronous proposal generation."""

import asyncio
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from backend import database
from backend.database import OutboxEvent, utc_now

from .generator import ProposalData, ProposalGenerator

_TOPIC = "proposal.generate"


async def proposal_worker(*, poll_interval: float = 2.0) -> None:
    """Poll and process proposal.generate events serially."""
    while True:
        try:
            await _process_one()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("proposal worker iteration failed")
        await asyncio.sleep(poll_interval)


async def _process_one() -> bool:
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        event = (
            await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.topic == _TOPIC, OutboxEvent.status == "PENDING")
                .order_by(OutboxEvent.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalars().first()
        if event is None:
            return False
        event.status = "IN_PROGRESS"
        event.attempts += 1
        await session.commit()
        try:
            payload = event.payload or {}
            proposal = await ProposalGenerator().generate(
                session,
                ProposalData(
                    lead_id=UUID(str(payload["lead_id"])),
                    meeting_notes=str(payload.get("meeting_notes", "")),
                    package_name=payload.get("package_name"),
                    service_type=payload.get("service_type"),
                ),
            )
            session.add(
                OutboxEvent(
                    topic="notification.owner",
                    payload={"type": "proposal_ready", "proposal_id": str(proposal.id)},
                )
            )
            event.status = "DONE"
            event.processed_at = utc_now()
            await session.commit()
        except Exception as exc:
            await session.rollback()
            event = await session.get(OutboxEvent, event.id)
            if event is not None:
                event.status = "FAILED"
                event.last_error = str(exc)[:1000]
                event.processed_at = utc_now()
                await session.commit()
            logger.error("proposal event {} failed: {}", event.id if event else "unknown", exc)
        return True
