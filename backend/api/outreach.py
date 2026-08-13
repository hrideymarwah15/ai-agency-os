"""Outreach API endpoints for campaign management."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import Integer, and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.owner import get_current_owner
from backend.config import settings
from backend.database import (
    Business,
    OutboxEvent,
    OutreachCampaign,
    OutreachLog,
    OutreachMessage,
    get_db,
)
from backend.services.outreach.sequence import SequenceEngine
from backend.services.outreach.clients import OutreachChannel
from backend.services.outreach.meeting_scheduler import meeting_scheduler
from backend.services.outreach.reply_classifier import ReplyClassification, reply_classifier
from backend.services.outreach.worker import OutreachWorker
from backend.services.audit import AuditService

router = APIRouter()
security = HTTPBearer()


# Pydantic models for request/response
class CampaignCreate(BaseModel):
    lead_id: UUID = Field(..., description="Business/lead ID to target")
    sequence_id: str = Field(..., description="Outreach sequence to use (e.g., 'cold_email_5touch')")

class CampaignResponse(BaseModel):
    id: UUID
    lead_id: UUID
    sequence_id: str
    channel: str
    current_step: int
    status: str  # ACTIVE, PAUSED, COMPLETED, BOUNCED, OPTED_OUT
    next_action_at: Optional[str] = None
    metrics: dict
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

class CampaignDetailResponse(CampaignResponse):
    messages: List[dict] = []
    logs: List[dict] = []

class MessageResponse(BaseModel):
    id: UUID
    step_number: int
    channel: str
    template_id: str
    rendered_subject: str
    rendered_content: str
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    opened_at: Optional[str] = None
    clicked_at: Optional[str] = None
    replied_at: Optional[str] = None
    reply_content: Optional[str] = None
    reply_classification: Optional[str] = None
    status: str

    class Config:
        from_attributes = True

class CampaignMetricsResponse(BaseModel):
    sent: int = 0
    delivered: int = 0
    opened: int = 0
    clicked: int = 0
    replied: int = 0
    bounced: int = 0
    unsubscribed: int = 0
    meetings_booked: int = 0

class PauseCampaignRequest(BaseModel):
    pass

class ResumeCampaignRequest(BaseModel):
    pass

class SkipStepRequest(BaseModel):
    pass


@router.post("/api/v1/outreach/campaigns", response_model=CampaignResponse)
async def create_campaign(
    campaign_data: CampaignCreate,
    background_tasks: BackgroundTasks,
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db)
):
    """Create a new outreach campaign for a lead."""
    # Verify the business/lead exists
    business_result = await session.execute(
        select(Business).where(Business.id == campaign_data.lead_id)
    )
    business = business_result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Verify sequence exists
    sequence_engine = SequenceEngine()
    try:
        sequence_engine.load_sequence(campaign_data.sequence_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Sequence '{campaign_data.sequence_id}' not found")

    # Check if there's already an active campaign for this lead/sequence
    existing_result = await session.execute(
        select(OutreachCampaign).where(
            and_(
                OutreachCampaign.lead_id == campaign_data.lead_id,
                OutreachCampaign.sequence_id == campaign_data.sequence_id,
                OutreachCampaign.status.in_(["ACTIVE", "PAUSED"])
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Active campaign already exists for this lead and sequence"
        )

    # Create new campaign
    campaign = OutreachCampaign(
        lead_id=campaign_data.lead_id,
        sequence_id=campaign_data.sequence_id,
        channel="EMAIL",  # Default - could be determined by sequence or business data
        current_step=1,
        status="ACTIVE",
        next_action_at=datetime.now(timezone.utc),  # Send immediately
        metrics={}
    )
    session.add(campaign)
    await session.flush()  # Get the ID

    # Schedule first outreach send via outbox
    outbox_event = OutboxEvent(
        topic="outreach.send",
        payload={
            "campaign_id": str(campaign.id),
            "lead_id": str(campaign_data.lead_id),
            "step_number": 1,
            "channel": campaign.channel,
            "personalization_data": {
                "lead": {
                    "id": str(business.id),
                    "name": business.name or "",
                    "company": business.name or "",
                    "industry": business.industry or "",
                    "location": business.location or "",
                    "website": business.website or "",
                    "employees": business.employees or 0,
                    "reviews": business.reviews or 0,
                    "rating": business.rating or 0.0,
                    "pain_point": business.pain_point or "",
                    "competitor": business.competitor or "",
                    "compliment": business.compliment or ""
                },
                "owner": {
                    "name": settings.agency_name,
                    "calendar_link": getattr(settings, 'owner_calendar_link', '')
                }
            }
        }
    )
    session.add(outbox_event)
    await session.flush()  # Get the ID

    # For MVP, we'll also process the event immediately to avoid requiring a separate worker
    # In production, this would be handled by the outreach worker
    try:
        worker = OutreachWorker()
        await worker._process_outreach_send_event(session, outbox_event)
    except Exception as e:
        # If immediate processing fails, the event remains in PENDING state
        # and will be picked up by the worker on the next cycle
        pass

    await session.commit()

    # Process the first send immediately for demo purposes
    background_tasks.add_task(
        process_campaign_step,
        campaign_id=str(campaign.id),
        lead_id=str(campaign_data.lead_id),
        step_number=1,
        channel=campaign.channel
    )

    return CampaignResponse.from_orm(campaign)


@router.get("/api/v1/outreach/campaigns", response_model=List[CampaignResponse])
async def list_campaigns(
    status: Optional[str] = Query(None, description="Filter by campaign status"),
    lead_id: Optional[UUID] = Query(None, description="Filter by lead ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db)
):
    """List outreach campaigns with optional filtering."""
    query = select(OutreachCampaign)

    if status:
        query = query.where(OutreachCampaign.status == status)
    if lead_id:
        query = query.where(OutreachCampaign.lead_id == lead_id)

    query = query.order_by(desc(OutreachCampaign.created_at)).limit(limit).offset(offset)

    result = await session.execute(query)
    campaigns = result.scalars().all()

    return [CampaignResponse.from_orm(c) for c in campaigns]


@router.get("/api/v1/outreach/campaigns/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    campaign_id: UUID = Path(...),
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific campaign."""
    # Get campaign
    campaign_result = await session.execute(
        select(OutreachCampaign).where(OutreachCampaign.id == campaign_id)
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get messages for this campaign
    messages_result = await session.execute(
        select(OutreachMessage)
        .where(OutreachMessage.campaign_id == campaign_id)
        .order_by(OutreachMessage.step_number)
    )
    messages = messages_result.scalars().all()

    # Get logs for this campaign
    logs_result = await session.execute(
        select(OutreachLog)
        .where(OutreachLog.campaign_id == campaign_id)
        .order_by(desc(OutreachLog.sent_at))
        .limit(50)  # Limit logs for performance
    )
    logs = logs_result.scalars().all()

    # Build response
    response = CampaignDetailResponse.from_orm(campaign)
    response.messages = [MessageResponse.from_orm(m) for m in messages]
    response.logs = [
        {
            "id": str(log.id),
            "channel": log.channel,
            "direction": log.direction,
            "subject": log.subject,
            "status": log.status,
            "sent_at": log.sent_at.isoformat() if log.sent_at else None,
            "responded_at": log.responded_at.isoformat() if log.responded_at else None
        }
        for log in logs
    ]

    return response


@router.post("/api/v1/outreach/campaigns/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: UUID = Path(...),
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db)
):
    """Pause an active campaign."""
    campaign_result = await session.execute(
        select(OutreachCampaign).where(OutreachCampaign.id == campaign_id)
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Only active campaigns can be paused")

    campaign.status = "PAUSED"
    campaign.next_action_at = None  # Clear scheduled time
    await session.commit()

    await AuditService.record(
        session,
        actor=owner.get("id", "unknown"),
        action="outreach.campaign.paused",
        entity_type="outreach_campaign",
        entity_id=str(campaign_id),
        payload={}
    )

    return CampaignResponse.from_orm(campaign)


@router.post("/api/v1/outreach/campaigns/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: UUID = Path(...),
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Resume a paused campaign."""
    campaign_result = await session.execute(
        select(OutreachCampaign).where(OutreachCampaign.id == campaign_id)
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status != "PAUSED":
        raise HTTPException(status_code=400, detail="Only paused campaigns can be resumed")

    campaign.status = "ACTIVE"
    # Set next action to now (or calculate based on current step)
    campaign.next_action_at = datetime.now(timezone.utc)
    await session.commit()

    # Schedule next step if applicable
    if campaign.current_step > 0:  # Has started
        background_tasks.add_task(
            process_campaign_step,
            campaign_id=str(campaign.id),
            lead_id=str(campaign.lead_id),
            step_number=campaign.current_step,
            channel=campaign.channel
        )

    await AuditService.record(
        session,
        actor=owner.get("id", "unknown"),
        action="outreach.campaign.resumed",
        entity_type="outreach_campaign",
        entity_id=str(campaign_id),
        payload={}
    )

    return CampaignResponse.from_orm(campaign)


@router.post("/api/v1/outreach/campaigns/{campaign_id}/skip-step", response_model=CampaignResponse)
async def skip_step(
    campaign_id: UUID = Path(...),
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Skip the current step and move to the next one."""
    campaign_result = await session.execute(
        select(OutreachCampaign).where(OutreachCampaign.id == campaign_id)
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Only active campaigns can skip steps")

    # Move to next step
    campaign.current_step += 1

    # Check if sequence is complete
    sequence_engine = SequenceEngine()
    try:
        sequence_config = sequence_engine.load_sequence(campaign.sequence_id)
        next_template = sequence_engine.get_step_template(campaign.sequence_id, campaign.current_step)
        if not next_template:
            # Sequence completed
            campaign.status = "COMPLETED"
            campaign.next_action_at = None
        else:
            # Calculate delay for next step
            delay_days = 0
            for step in sequence_config.steps:
                if step.step == campaign.current_step:
                    delay_days = step.delay_days
                    break
            campaign.next_action_at = datetime.now(timezone.utc) + timedelta(days=delay_days)
    except Exception:
        # If sequence not found, mark as failed
        campaign.status = "FAILED"
        campaign.next_action_at = None

    await session.commit()

    # Schedule next step if still active
    if campaign.status == "ACTIVE" and campaign.next_action_at:
        background_tasks.add_task(
            process_campaign_step,
            campaign_id=str(campaign.id),
            lead_id=str(campaign.lead_id),
            step_number=campaign.current_step,
            channel=campaign.channel
        )

    await AuditService.record(
        session,
        actor=owner.get("id", "unknown"),
        action="outreach.campaign.step_skipped",
        entity_type="outreach_campaign",
        entity_id=str(campaign_id),
        payload={"skipped_step": campaign.current_step - 1}
    )

    return CampaignResponse.from_orm(campaign)


@router.get("/api/v1/outreach/campaigns/{campaign_id}/metrics", response_model=CampaignMetricsResponse)
async def get_campaign_metrics(
    campaign_id: UUID = Path(...),
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db)
):
    """Get engagement metrics for a campaign."""
    # Get message stats
    messages_result = await session.execute(
        select(
            func.count(OutreachMessage.id).label("total"),
            func.sum(func.cast(OutreachMessage.status == "SENT", Integer)).label("sent"),
            func.sum(func.cast(OutreachMessage.status == "DELIVERED", Integer)).label("delivered"),
            func.sum(func.cast(OutreachMessage.status == "OPENED", Integer)).label("opened"),
            func.sum(func.cast(OutreachMessage.status == "CLICKED", Integer)).label("clicked"),
            func.sum(func.cast(OutreachMessage.status == "REPLIED", Integer)).label("replied")
        ).where(OutreachMessage.campaign_id == campaign_id)
    )
    msg_stats = messages_result.first()

    # Get log stats for bounces/unsubscribes
    logs_result = await session.execute(
        select(
            func.sum(func.cast(OutreachLog.status == "BOUNCED", Integer)).label("bounced"),
            func.sum(func.cast(OutreachLog.status == "OPTED_OUT", Integer)).label("unsubscribed")
        ).where(
            and_(
                OutreachLog.campaign_id == campaign_id,
                OutreachLog.direction == "OUTBOUND"
            )
        )
    )
    log_stats = logs_result.first()

    # For demo purposes, we'll estimate meetings booked (in real system, this would come from replies/meetings)
    meetings_estimate = min((msg_stats.replied or 0) // 2, 5)  # Rough estimate

    return CampaignMetricsResponse(
        sent=msg_stats.sent or 0,
        delivered=msg_stats.delivered or 0,
        opened=msg_stats.opened or 0,
        clicked=msg_stats.clicked or 0,
        replied=msg_stats.replied or 0,
        bounced=log_stats.bounced or 0,
        unsubscribed=log_stats.unsubscribed or 0,
        meetings_booked=meetings_estimate
    )


# Background task functions
async def process_campaign_step(campaign_id: str, lead_id: str, step_number: int, channel: str):
    """Background task to process a campaign step."""
    from backend import database

    if database.async_session_maker is None:
        return
    async with database.async_session_maker() as session:
        try:
            campaign_uuid = UUID(campaign_id)
            lead_uuid = UUID(lead_id)
            channel_enum = OutreachChannel(channel)

            # Use the worker's internal processing method
            worker = OutreachWorker()
            await worker._process_outreach_send(
                session, campaign_uuid, lead_uuid, step_number, channel_enum, {}, 0
            )
        except Exception as e:
            # Log error but don't crash the background task
            print(f"Error processing campaign step: {e}")
            try:
                await AuditService.record(
                    session,
                    actor="system",
                    action="outreach.background_task.error",
                    entity_type="outreach_campaign",
                    entity_id=campaign_id,
                    payload={"error": str(e)[:200]}
                )
                await session.commit()
            except:
                pass


@router.post("/api/v1/outreach/reply-webhook")
async def handle_reply_webhook(
    campaign_id: UUID = Query(...),
    lead_id: UUID = Query(...),
    reply_content: str = Query(...),
    channel: str = Query(...),
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db)
):
    """
    Handle incoming reply webhook from email or LinkedIn.
    Classifies the reply and triggers appropriate follow-up actions.
    """
    # Verify the campaign and lead exist
    campaign_result = await session.execute(
        select(OutreachCampaign).where(
            and_(
                OutreachCampaign.id == campaign_id,
                OutreachCampaign.lead_id == lead_id
            )
        )
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Classify the reply using the reply classifier
    classification_result = reply_classifier.classify(reply_content)

    # Audit the classification
    await AuditService.record(
        session,
        actor="system",
        action="outreach.reply.classified",
        entity_type="outreach_campaign",
        entity_id=str(campaign_id),
        payload={
            "lead_id": str(lead_id),
            "reply_content": reply_content[:200],  # Truncate for storage
            "classification": classification_result.classification.value,
            "confidence": classification_result.confidence,
            "reasoning": classification_result.reasoning,
            "escalate_to_owner": classification_result.escalate_to_owner
        }
    )

    # If confidence is low, escalate to owner
    if classification_result.escalate_to_owner:
        await AuditService.record(
            session,
            actor="system",
            action="outreach.reply.escalated",
            entity_type="outreach_campaign",
            entity_id=str(campaign_id),
            payload={
                "lead_id": str(lead_id),
                "reply_content": reply_content[:200],
                "classification": classification_result.classification.value,
                "confidence": classification_result.confidence
            }
        )
        # In a full implementation, this would notify the owner via dashboard alert, email, etc.
        # For now, we just log it

    # If we have a suggested response and confidence is high enough, send it
    if (classification_result.suggested_response and
        classification_result.confidence >= 0.8 and
        not classification_result.escalate_to_owner):

        # Send the suggested response as a follow-up message
        # Determine next step based on classification
        next_step_number = campaign.current_step + 1
        next_action_at = datetime.now(timezone.utc) + timedelta(hours=1)  # Send soon

        # Update campaign state
        campaign.current_step = next_step_number
        campaign.next_action_at = next_action_at

        # Create the follow-up message
        outreach_message = OutreachMessage(
            campaign_id=campaign_id,
            step_number=next_step_number,
            channel=channel,
            template_id="auto_response",  # Special template for auto-responses
            rendered_subject=f"Re: {classification_result.suggested_response[:50]}",
            rendered_content=classification_result.suggested_response,
            personalization_data={},  # Would be populated with lead/owner data
            sent_at=datetime.now(timezone.utc),
            status="SENT"
        )
        session.add(outreach_message)

        # Log the outreach
        outreach_log = OutreachLog(
            business_id=lead_id,
            campaign_id=campaign_id,
            channel=channel,
            direction="OUTBOUND",
            subject=outreach_message.rendered_subject,
            content=outreach_message.rendered_content,
            status="SENT",
            sent_at=datetime.now(timezone.utc)
        )
        session.add(outreach_log)

        # Audit the auto-response send
        await AuditService.record(
            session,
            actor="system",
            action="outreach.reply.auto_responded",
            entity_type="outreach_campaign",
            entity_id=str(campaign_id),
            payload={
                "lead_id": str(lead_id),
                "original_reply": reply_content[:200],
                "classification": classification_result.classification.value,
                "suggested_response": classification_result.suggested_response[:200]
            }
        )

        await session.commit()

        # Schedule next step via outbox
        new_event = OutboxEvent(
            topic="outreach.send",
            payload={
                "campaign_id": str(campaign_id),
                "lead_id": str(lead_id),
                "step_number": next_step_number,
                "channel": channel,
                "personalization_data": {}
            }
        )
        session.add(new_event)
        await session.commit()

    # Handle specific classifications that require special actions
    if classification_result.classification == ReplyClassification.MEETING_BOOKED:
        # Extract meeting details from reply and book via Cal.com
        # This would involve parsing the reply for meeting details
        pass

    elif classification_result.classification == ReplyClassification.OBJECTION:
        # Objection already handled by suggested response above if confidence high enough
        pass

    return {"status": "processed", "classification": classification_result.classification.value}


@router.post("/api/v1/outreach/meetings/book")
async def book_meeting(
    campaign_id: UUID = Query(...),
    lead_id: UUID = Query(...),
    preferred_time: str = Query(...),  # ISO format datetime
    attendee_name: str = Query(...),
    attendee_email: str = Query(...),
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db)
):
    """
    Book a meeting with a lead via Cal.com integration.
    """
    # Verify the campaign and lead exist
    campaign_result = await session.execute(
        select(OutreachCampaign).where(
            and_(
                OutreachCampaign.id == campaign_id,
                OutreachCampaign.lead_id == lead_id
            )
        )
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Parse the preferred time
    try:
        meeting_time = datetime.fromisoformat(preferred_time.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    # Book the meeting via Cal.com
    booking_result = await meeting_scheduler.book_meeting(
        start_time=meeting_time,
        attendee_name=attendee_name,
        attendee_email=attendee_email,
        notes=f"Campaign {campaign_id}, Lead {lead_id}"
    )

    if booking_result.success:
        # Audit the booking
        await AuditService.record(
            session,
            actor=owner.get("id", "unknown"),
            action="outreach.meeting.booked",
            entity_type="outreach_campaign",
            entity_id=str(campaign_id),
            payload={
                "lead_id": str(lead_id),
                "meeting_time": preferred_time,
                "attendee_name": attendee_name,
                "attendee_email": attendee_email,
                "booking_id": booking_result.booking_id,
                "booking_url": booking_result.booking_url
            }
        )

        # Update campaign with meeting info (could add meeting tracking to campaign model)
        # For now, we just audit it

        return {
            "status": "success",
            "booking_id": booking_result.booking_id,
            "booking_url": booking_result.booking_url,
            "meeting_time": preferred_time
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to book meeting: {booking_result.error}"
        )


@router.get("/api/v1/outreach/meetings")
async def get_meetings(
    campaign_id: Optional[UUID] = Query(None),
    lead_id: Optional[UUID] = Query(None),
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db)
):
    """
    Get meetings for a campaign or lead.
    In a full implementation, this would query a meetings table.
    For MVP, we return a placeholder response.
    """
    # Verify ownership if campaign_id or lead_id provided
    if campaign_id:
        campaign_result = await session.execute(
            select(OutreachCampaign).where(OutreachCampaign.id == campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

    if lead_id:
        from backend.database import Business
        lead_result = await session.execute(
            select(Business).where(Business.id == lead_id)
        )
        lead = lead_result.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

    # In a full implementation, we would query a meetings table
    # For MVP, we return placeholder data
    return {
        "meetings": [],
        "total": 0,
        "filters": {
            "campaign_id": str(campaign_id) if campaign_id else None,
            "lead_id": str(lead_id) if lead_id else None
        }
    }


@router.post("/api/v1/outreach/calendly-webhook")
async def handle_calendly_webhook(
    request: Request,
    owner: dict = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db)
):
    """
    Handle incoming webhook from Cal.com for meeting events.
    """
    try:
        webhook_data = await request.json()

        # Process the webhook via the meeting scheduler
        result = await meeting_scheduler.handle_webhook(webhook_data)

        if result.get("processed"):
            # Audit the webhook processing
            await AuditService.record(
                session,
                actor="system",
                action="outreach.meeting.webhook.processed",
                entity_type="outreach_campaign",
                entity_id=str(result.get("booking_id", "unknown")),
                payload=result
            )

        return {"status": "processed", "result": result}

    except Exception as e:
        await AuditService.record(
            session,
            actor="system",
            action="outreach.meeting.webhook.error",
            entity_type="outreach_campaign",
            entity_id="unknown",
            payload={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=str(e))
