"""Durable outbox worker for asynchronous proposal generation."""

import asyncio
from datetime import timedelta
from uuid import UUID

from loguru import logger
from sqlalchemy import or_, select

from backend import database
from backend.database import Business, BusinessStatus, OutboxEvent, Proposal, ProposalStatus, utc_now
from backend.services.audit import AuditService
from backend.services.outreach.clients import SendGridClient

from .generator import ProposalData, ProposalGenerator

_TOPIC = "proposal.generate"
_DELIVERY_TOPIC = "proposal.deliver"
_STALE_AFTER = timedelta(minutes=10)


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
        await _recover_stale(session)
        event = (
            await session.execute(
                select(OutboxEvent)
                .where(
                    OutboxEvent.topic.in_([_TOPIC, _DELIVERY_TOPIC]),
                    OutboxEvent.status == "PENDING",
                    or_(OutboxEvent.next_run_at.is_(None), OutboxEvent.next_run_at <= utc_now()),
                )
                .order_by(OutboxEvent.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalars().first()
        if event is None:
            return False
        event.status = "IN_PROGRESS"
        event.attempts += 1
        event.next_run_at = utc_now()
        await session.commit()
        try:
            payload = event.payload or {}
            if event.topic == _TOPIC:
                proposal = await ProposalGenerator().generate(
                    session,
                    ProposalData(
                        lead_id=UUID(str(payload["lead_id"])),
                        meeting_notes=str(payload.get("meeting_notes", "")),
                        package_name=payload.get("package_name"),
                        service_type=payload.get("service_type"),
                    ),
                )
                session.add(OutboxEvent(topic="notification.owner", payload={"type": "proposal_ready", "proposal_id": str(proposal.id)}))
            else:
                await _deliver(session, event)
            event.status = "DONE"
            event.processed_at = utc_now()
            await session.commit()
        except Exception as exc:
            await session.rollback()
            event = await session.get(OutboxEvent, event.id)
            if event is not None:
                event.status = "PENDING" if event.attempts < 3 else "FAILED"
                event.last_error = str(exc)[:1000]
                event.processed_at = utc_now() if event.status == "FAILED" else None
                event.next_run_at = utc_now() + timedelta(seconds=30) if event.status == "PENDING" else None
                await session.commit()
            logger.error("proposal event {} failed: {}", event.id if event else "unknown", exc)
        return True


async def _recover_stale(session) -> None:
    """Return abandoned claims to PENDING so a worker restart can retry them."""
    cutoff = utc_now() - _STALE_AFTER
    result = await session.execute(
        select(OutboxEvent).where(
            OutboxEvent.topic.in_([_TOPIC, _DELIVERY_TOPIC]),
            OutboxEvent.status == "IN_PROGRESS",
            OutboxEvent.next_run_at < cutoff,
        )
    )
    for event in result.scalars().all():
        event.status = "PENDING"
        event.last_error = "Recovered stale in-progress proposal event"
        event.next_run_at = None
    await session.commit()


async def _deliver(session, event: OutboxEvent) -> None:
    """Send one proposal through the existing provider and transition after success."""
    payload = event.payload or {}
    proposal = await session.get(Proposal, UUID(str(payload["proposal_id"])))
    if proposal is None:
        raise ValueError("Proposal not found")
    if proposal.status == ProposalStatus.SENT:
        return
    business = await session.get(Business, proposal.business_id)
    if business is None or not business.email:
        raise ValueError("Client email is required for proposal delivery")
    client = SendGridClient()
    await client.send_email(
        to_email=business.email,
        to_name=business.decision_maker or business.name,
        subject=f"Proposal for {business.name}",
        html_content=proposal.full_html or "",
        text_content=f"Proposal for {business.name}: {proposal.executive_summary or proposal.scope_summary}",
        campaign_id=str(proposal.id),
        message_id=str(event.id),
        audit_session=session,
    )
    proposal.status = ProposalStatus.SENT
    proposal.sent_at = utc_now()
    business.status = BusinessStatus.NEGOTIATING
    await AuditService.record(
        session,
        actor="system",
        action="proposal.sent",
        entity_type="proposal",
        entity_id=str(proposal.id),
        correlation_id=str(proposal.id),
        payload={"outbox_event_id": str(event.id), "provider": "sendgrid"},
    )
