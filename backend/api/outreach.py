"""Owner outreach campaign, automation configuration, and webhook API."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.owner import get_current_owner
from backend.database import (
    Business,
    OutboxEvent,
    OutreachCampaign,
    OutreachMeeting,
    OutreachMessage,
    get_db,
)
from backend.services.audit import AuditService
from backend.services.discovery.sanitize import strip_control_tokens
from backend.services.outreach.meeting_scheduler import meeting_scheduler
from backend.services.outreach.reply_classifier import reply_classifier
from backend.services.outreach.sequence import SequenceEngine
from backend.services.outreach.worker import OutreachWorker

router = APIRouter()
CONFIG_PATH = Path("backend/config/outreach.yaml")


class CampaignCreate(BaseModel):
    """Campaign creation input."""

    lead_id: UUID
    sequence_id: str


class ReplyWebhook(BaseModel):
    """Normalized provider reply callback body."""

    campaign_id: UUID
    lead_id: UUID
    reply_content: str
    channel: str = "email"


class DirectBooking(BaseModel):
    """Direct Cal.com booking input."""

    campaign_id: UUID
    start_time: datetime
    attendee_name: str
    attendee_email: str


def _campaign_view(campaign: OutreachCampaign) -> dict[str, Any]:
    return {
        "id": str(campaign.id),
        "lead_id": str(campaign.lead_id),
        "sequence_id": campaign.sequence_id,
        "channel": campaign.channel,
        "current_step": campaign.current_step,
        "status": campaign.status,
        "next_action_at": campaign.next_action_at.isoformat() if campaign.next_action_at else None,
        "metrics": campaign.metrics or {},
        "created_at": campaign.created_at.isoformat(),
        "updated_at": campaign.updated_at.isoformat(),
    }


@router.post("/api/v1/outreach/campaigns", status_code=201)
async def create_campaign(
    body: CampaignCreate,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a campaign and enqueue its first durable send."""
    business = await session.get(Business, body.lead_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    try:
        sequence = SequenceEngine().load_sequence(body.sequence_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    campaign = OutreachCampaign(
        lead_id=body.lead_id,
        sequence_id=body.sequence_id,
        channel=sequence.channel.lower(),
        current_step=1,
        status="ACTIVE",
        next_action_at=datetime.now(UTC),
        metrics={},
    )
    session.add(campaign)
    await session.flush()
    session.add(
        OutboxEvent(
            topic="outreach.send",
            payload={
                "campaign_id": str(campaign.id),
                "lead_id": str(body.lead_id),
                "step_number": 1,
                "channel": campaign.channel,
                "personalization_data": {},
            },
        )
    )
    await session.commit()
    return _campaign_view(campaign)


@router.get("/api/v1/outreach/campaigns")
async def list_campaigns(
    status: str | None = None,
    lead_id: UUID | None = None,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List campaigns with optional status and lead filters."""
    stmt = select(OutreachCampaign)
    if status:
        stmt = stmt.where(OutreachCampaign.status == status)
    if lead_id:
        stmt = stmt.where(OutreachCampaign.lead_id == lead_id)
    rows = (await session.execute(stmt.order_by(desc(OutreachCampaign.created_at)))).scalars()
    return [_campaign_view(row) for row in rows]


async def _campaign_or_404(session: AsyncSession, campaign_id: UUID) -> OutreachCampaign:
    campaign = await session.get(OutreachCampaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/api/v1/outreach/campaigns/{campaign_id}")
async def campaign_detail(
    campaign_id: UUID,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return campaign and message history."""
    campaign = await _campaign_or_404(session, campaign_id)
    messages = (
        await session.execute(
            select(OutreachMessage)
            .where(OutreachMessage.campaign_id == campaign_id)
            .order_by(OutreachMessage.step_number)
        )
    ).scalars()
    view = _campaign_view(campaign)
    view["messages"] = [
        {
            "id": str(message.id),
            "step_number": message.step_number,
            "status": message.status,
            "reply_classification": message.reply_classification,
            "replied_at": message.replied_at.isoformat() if message.replied_at else None,
        }
        for message in messages
    ]
    return view


@router.post("/api/v1/outreach/campaigns/{campaign_id}/{action}")
async def campaign_action(
    campaign_id: UUID,
    action: str,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Pause, resume, or skip a campaign step."""
    campaign = await _campaign_or_404(session, campaign_id)
    if action == "pause":
        campaign.status = "PAUSED"
        campaign.next_action_at = None
    elif action == "resume":
        campaign.status = "ACTIVE"
        campaign.next_action_at = datetime.now(UTC)
    elif action == "skip-step":
        campaign.current_step += 1
        if SequenceEngine().get_step_template(campaign.sequence_id, campaign.current_step) is None:
            campaign.status = "COMPLETED"
            campaign.next_action_at = None
    else:
        raise HTTPException(status_code=404, detail="Unknown campaign action")
    await AuditService.record(
        session,
        actor="owner",
        action=f"outreach.campaign.{action}",
        entity_type="outreach_campaign",
        entity_id=str(campaign.id),
        payload={},
        correlation_id=str(campaign.id),
    )
    await session.commit()
    return _campaign_view(campaign)


@router.post("/api/v1/outreach/reply-webhook")
async def reply_webhook(
    body: ReplyWebhook,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Classify and orchestrate a normalized inbound provider reply."""
    campaign = await _campaign_or_404(session, body.campaign_id)
    if campaign.lead_id != body.lead_id:
        raise HTTPException(status_code=400, detail="Lead does not match campaign")
    clean = strip_control_tokens(body.reply_content)[:20_000]
    return await OutreachWorker().handle_reply(
        session, campaign, clean, {"channel": body.channel}
    )


@router.post("/api/v1/outreach/events/{trigger_event}")
async def trigger_follow_up(
    trigger_event: str,
    campaign_id: UUID = Query(...),
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Enqueue an event-matched follow-up."""
    campaign = await _campaign_or_404(session, campaign_id)
    return {"enqueued": await OutreachWorker().enqueue_follow_up(session, campaign, trigger_event)}


@router.post("/api/v1/outreach/meetings/book")
async def book_meeting(
    body: DirectBooking,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Book directly through Cal.com and persist the result."""
    campaign = await _campaign_or_404(session, body.campaign_id)
    result = await meeting_scheduler.create_booking_direct(
        body.start_time,
        body.attendee_email,
        body.attendee_name,
        custom_fields={"campaign_id": str(campaign.id)},
    )
    meeting = OutreachMeeting(
        campaign_id=campaign.id,
        booking_id=result.booking_id,
        lead_email=body.attendee_email,
        start_time=result.start_time,
        end_time=result.end_time,
        meeting_url=result.meeting_url,
        status="BOOKED",
    )
    session.add(meeting)
    await session.commit()
    return {"booking_id": result.booking_id, "meeting_url": result.meeting_url}


@router.get("/api/v1/outreach/meetings")
async def list_meetings(
    campaign_id: UUID | None = None,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List persisted meetings."""
    stmt = select(OutreachMeeting)
    if campaign_id:
        stmt = stmt.where(OutreachMeeting.campaign_id == campaign_id)
    rows = (await session.execute(stmt.order_by(desc(OutreachMeeting.start_time)))).scalars()
    return [
        {
            "booking_id": row.booking_id,
            "campaign_id": str(row.campaign_id),
            "lead_email": row.lead_email,
            "start_time": row.start_time.isoformat(),
            "status": row.status,
        }
        for row in rows
    ]


@router.post("/api/v1/outreach/meetings/webhook")
async def meeting_webhook(
    request: Request,
) -> dict[str, Any]:
    """Verify Cal.com HMAC, persist booking, and enqueue proposal generation."""
    raw = await request.body()
    signature = request.headers.get("x-cal-signature-256", "")
    if not meeting_scheduler.verify_webhook(raw, signature):
        raise HTTPException(status_code=401, detail="Invalid Cal.com webhook signature")
    from backend import database

    if database.async_session_maker is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    payload = json.loads(raw)
    event = meeting_scheduler.handle_webhook(payload)
    campaign_id = payload.get("payload", {}).get("metadata", {}).get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="campaign_id metadata is required")
    async with database.async_session_maker() as session:
        campaign = await _campaign_or_404(session, UUID(str(campaign_id)))
        await OutreachWorker().handle_meeting_event(session, campaign, event)
    return {"processed": True, "booking_id": event.booking_id, "event": event.type.value}


def _load_config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text()) or {}


def _save_config(data: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(yaml.safe_dump(data, sort_keys=False))


@router.get("/api/v1/outreach/sequences")
async def list_sequences(_owner: str = Depends(get_current_owner)) -> dict[str, Any]:
    """List validated sequences for the editor."""
    engine = SequenceEngine()
    return {
        "sequences": [
            {"id": key, "channel": value.channel, "steps": [s.model_dump() for s in value.steps]}
            for key, value in engine._sequences.items()
        ]
    }


@router.put("/api/v1/outreach/sequences/{sequence_id}")
async def update_sequence(
    sequence_id: str,
    body: dict[str, Any],
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Validate and rewrite one sequence."""
    data = _load_config()
    if sequence_id not in data.get("sequences", {}):
        raise HTTPException(status_code=404, detail="Sequence not found")
    from backend.services.outreach.sequence import SequenceConfig, SequenceStep

    SequenceConfig(channel=body["channel"], steps=[SequenceStep(**s) for s in body["steps"]])
    data["sequences"][sequence_id] = body
    _save_config(data)
    await AuditService.record(
        session,
        actor="owner",
        action="outreach.sequence.updated",
        entity_type="outreach_sequence",
        entity_id=sequence_id,
        payload={"step_count": len(body["steps"])},
    )
    await session.commit()
    return {"id": sequence_id, **body}


@router.get("/api/v1/outreach/objections")
async def list_objections(_owner: str = Depends(get_current_owner)) -> dict[str, Any]:
    """List objection library."""
    return {"objections": _load_config().get("objection_responses", {})}


@router.put("/api/v1/outreach/objections/{objection_type}")
async def update_objection(
    objection_type: str,
    body: dict[str, str],
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Rewrite and audit one objection response."""
    data = _load_config()
    if objection_type not in data.get("objection_responses", {}):
        raise HTTPException(status_code=404, detail="Objection type not found")
    template = body.get("template", "").strip()
    if not template:
        raise HTTPException(status_code=422, detail="template is required")
    data["objection_responses"][objection_type] = template
    _save_config(data)
    await AuditService.record(
        session,
        actor="owner",
        action="outreach.objection.updated",
        entity_type="outreach_objection",
        entity_id=objection_type,
        payload={"template_sha256": hashlib.sha256(template.encode()).hexdigest()},
    )
    await session.commit()
    return {"objection_type": objection_type, "template": template}


@router.get("/api/v1/outreach/meetings/config")
async def meeting_config(_owner: str = Depends(get_current_owner)) -> dict[str, Any]:
    """Return non-secret Cal.com owner configuration status."""
    return {
        "configured": meeting_scheduler.configured,
        "username": meeting_scheduler.username,
        "event_type_id": meeting_scheduler.event_type_id,
        "api_key_configured": bool(meeting_scheduler.api_key),
        "webhook_secret_configured": bool(meeting_scheduler.webhook_secret),
    }
