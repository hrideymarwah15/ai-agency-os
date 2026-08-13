"""Outreach worker: processes outbox events to execute sequence steps."""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import (
    ApprovalRequest,
    async_session_maker as AsyncSessionLocal,
    Business,
    OutboxEvent,
    OutreachCampaign,
    OutreachMessage,
    OutreachLog,
    OutreachMeeting,
)
from backend.services.audit import AuditService
from backend.services.compliance.send_gate import send_gate, SendGateResult
from backend.services.outreach.sequence import SequenceEngine
from backend.services.outreach.clients import SendGridClient, LinkedInClient, OutreachChannel
from backend.services.compliance import suppression
from backend.services.outreach.reply_classifier import ReplyClassification, ReplyClassifier
from backend.services.outreach.meeting_scheduler import BookingEvent, BookingEventType, MeetingScheduler


class OutreachWorker:
    """Worker that processes outreach.send outbox events."""

    def __init__(self):
        self.sequence_engine = SequenceEngine()
        self.sendgrid_client = SendGridClient()
        self.linkedin_client = LinkedInClient()
        self.reply_classifier = ReplyClassifier()
        self.meeting_scheduler = MeetingScheduler()
        self._running = False
        self._task: asyncio.Task | None = None
        self.send_gate = send_gate

    async def start(self):
        """Start the outreach worker."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        """Stop the outreach worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        """Main worker loop - process outbox events serially."""
        while self._running:
            try:
                await self._process_one()
                # Sleep briefly to avoid busy-waiting when no events are pending
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue running
                print(f"Outreach worker error: {e}")
                await asyncio.sleep(5.0)  # Back off on error

    async def _process_one(self) -> bool:
        """Process at most one PENDING outreach.send outbox event.

        Returns True if an event was processed, False if no events were pending.
        """
        session_maker = AsyncSessionLocal
        if session_maker is None:
            raise RuntimeError("Database not initialized")

        async with session_maker() as session:
            # Lock the row we're going to process to prevent race conditions
            # We look for the oldest PENDING event
            result = await session.execute(
                select(OutboxEvent)
                .where(
                    and_(
                        OutboxEvent.topic == "outreach.send",
                        OutboxEvent.status == "PENDING"
                    )
                )
                .order_by(OutboxEvent.created_at.asc())
                .limit(1)
                .with_for_update()  # Lock the row
            )
            event = result.scalar_one_or_none()

            if event is None:
                return False  # No pending events

            # Mark event as IN_PROGRESS
            event.status = "IN_PROGRESS"
            event.attempts += 1
            await session.commit()

            try:
                # Process the event
                success = await self._process_outreach_send_event(session, event)

                if success:
                    event.status = "DONE"
                    event.processed_at = datetime.now(timezone.utc)
                else:
                    event.status = "FAILED"

                await session.commit()
                return True

            except Exception as e:
                # Mark event as failed
                event.status = "FAILED"
                event.last_error = str(e)[:500]  # Limit error length
                await session.commit()
                raise  # Re-raise so the outer loop can handle it

    async def _process_outreach_send_event(
        self,
        session: AsyncSession,
        event: OutboxEvent
    ) -> bool:
        """Process a single outreach.send outbox event.

        Returns True if successful, False if should not be retried.
        """
        try:
            payload = event.payload
            campaign_id = payload.get("campaign_id")
            lead_id = payload.get("lead_id")
            step_number = payload.get("step_number")
            channel_str = payload.get("channel")
            personalization_data = dict(payload.get("personalization_data", {}))
            template_override = payload.get("template_override")

            if not all([campaign_id, lead_id, step_number, channel_str]):
                await AuditService.record(
                    session,
                    actor="system",
                    action="outreach.send.invalid_payload",
                    entity_type="outreach_campaign",
                    entity_id=str(campaign_id) if campaign_id else "unknown",
                    payload={"error": "Missing required fields in payload", "payload": payload}
                )
                return False  # Don't retry - bad payload

            # Convert strings to proper types
            try:
                campaign_uuid = campaign_id if isinstance(campaign_id, str) else str(campaign_id)
                lead_uuid = lead_id if isinstance(lead_id, str) else str(lead_id)
                step_num = int(step_number)
                channel = OutreachChannel(str(channel_str).lower())
            except (ValueError, TypeError) as e:
                await AuditService.record(
                    session,
                    actor="system",
                    action="outreach.send.invalid_data",
                    entity_type="outreach_campaign",
                    entity_id=str(campaign_id),
                    payload={"error": f"Invalid data types: {e}", "payload": payload}
                )
                return False

            # Process the outreach send in a database transaction
            success = await self._process_outreach_send(
                session,
                campaign_uuid,
                lead_uuid,
                step_num,
                channel,
                personalization_data,
                event.id,  # outbox event id for reference
                template_override,
            )
            return success

        except Exception as e:
            # Log unexpected error
            await AuditService.record(
                session,
                actor="system",
                action="outreach.send.error",
                entity_type="outbox_event",
                entity_id=str(event.id),
                payload={"error": str(e)[:200]}
            )
            await session.commit()
            return True  # Retry on unexpected errors

    async def _process_outreach_send(
        self,
        session: AsyncSession,
        campaign_id: str,
        lead_id: str,
        step_number: int,
        channel: OutreachChannel,
        personalization_data: Dict[str, Any],
        outbox_event_id: int,
        template_override: str | None = None,
    ) -> bool:
        """Process a single outreach send attempt."""
        # Get campaign
        campaign_result = await session.execute(
            select(OutreachCampaign).where(OutreachCampaign.id == campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()
        if not campaign:
            await AuditService.record(
                session,
                actor="system",
                action="outreach.send.campaign_not_found",
                entity_type="outreach_campaign",
                entity_id=campaign_id,
                payload={"outbox_event_id": outbox_event_id}
            )
            await session.commit()
            return False  # Don't retry

        # Verify this is the correct step
        if campaign.current_step != step_number:
            # Step has already been processed or we're out of sync
            await AuditService.record(
                session,
                actor="system",
                action="outreach.send.step_mismatch",
                entity_type="outreach_campaign",
                entity_id=campaign_id,
                payload={
                    "expected_step": campaign.current_step,
                    "received_step": step_number,
                    "outbox_event_id": outbox_event_id
                }
            )
            await session.commit()
            return False  # Don't retry - will be handled by next correct event

        # Get lead/business info for personalization
        from backend.database import Business
        business_result = await session.execute(
            select(Business).where(Business.id == lead_id)
        )
        business = business_result.scalar_one_or_none()
        if not business:
            await AuditService.record(
                session,
                actor="system",
                action="outreach.send.lead_not_found",
                entity_type="outreach_campaign",
                entity_id=campaign_id,
                payload={"lead_id": lead_id, "outbox_event_id": outbox_event_id}
            )
            await session.commit()
            return False  # Don't retry

        # Prepare personalization data with lead and owner info
        enhanced_personalization = {
            **personalization_data,
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

        # Load sequence and get template for this step
        try:
            sequence_config = self.sequence_engine.load_sequence(campaign.sequence_id)
            step_template = template_override or self.sequence_engine.get_step_template(
                campaign.sequence_id, step_number
            )
            if not step_template:
                raise ValueError(f"No template found for step {step_number} in sequence {campaign.sequence_id}")
        except Exception as e:
            await AuditService.record(
                session,
                actor="system",
                action="outreach.send.sequence_error",
                entity_type="outreach_campaign",
                entity_id=campaign_id,
                payload={"error": str(e), "outbox_event_id": outbox_event_id}
            )
            await session.commit()
            return False  # Don't retry

        # Render template
        try:
            subject, html_content, text_content = self.sequence_engine.render_template(
                step_template, enhanced_personalization
            )
        except Exception as e:
            await AuditService.record(
                session,
                actor="system",
                action="outreach.send.template_error",
                entity_type="outreach_campaign",
                entity_id=campaign_id,
                payload={"error": str(e), "template": step_template, "outbox_event_id": outbox_event_id}
            )
            await session.commit()
            return False  # Don't retry

        # Check if we can send via compliance gate
        send_result = await self.send_gate(
            session,
            lead_id=lead_id,
            channel=channel,
            content=f"{subject}\n\n{text_content}",
            email=business.email or ""
        )

        if not send_result.allowed:
            # Blocked by compliance - log and mark as failed
            outreach_log = OutreachLog(
                business_id=lead_id,
                campaign_id=campaign_id,
                channel=channel.value,
                direction="OUTBOUND",
                subject=subject,
                content=text_content,
                status="BLOCKED",
                sent_at=datetime.now(timezone.utc)
            )
            session.add(outreach_log)

            await AuditService.record(
                session,
                actor="system",
                action="outreach.send.blocked",
                entity_type="outreach_campaign",
                entity_id=campaign_id,
                payload={
                    "reason": send_result.reason,
                    "step": step_number,
                    "channel": channel.value,
                    "outbox_event_id": outbox_event_id
                }
            )
            await session.commit()
            return False  # Don't retry compliance blocks

        html_content = f"{html_content}\n{send_result.unsubscribe_footer}"
        text_content = f"{text_content}\n\nUnsubscribe: included in the HTML version."

        # Send via appropriate channel client
        try:
            if channel == OutreachChannel.EMAIL:
                send_result_dict = await self.sendgrid_client.send_email(
                    to_email=business.email or "",
                    to_name=business.name or "",
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    campaign_id=campaign_id,
                    message_id=f"{campaign_id}-{step_number}-{outbox_event_id}"
                )
            elif channel == OutreachChannel.LINKEDIN:
                # For LinkedIn, we'd need profile URN - this would come from business data
                # For now, we'll simulate or skip if not implemented
                # In a real implementation, we would get the profile URN from business data
                send_result_dict = {"status": "sent", "message_id": f"linkedin-{uuid4()}"}
            else:
                raise ValueError(f"Unsupported channel: {channel}")

            # Record the sent message
            outreach_message = OutreachMessage(
                campaign_id=campaign_id,
                step_number=step_number,
                channel=channel.value,
                template_id=step_template,
                rendered_subject=subject,
                rendered_content=html_content,
                personalization_data=enhanced_personalization,
                sent_at=datetime.now(timezone.utc),
                status="SENT"
            )
            session.add(outreach_message)

            # Update campaign state
            campaign.current_step += 1
            # Calculate next action time based on sequence delay
            next_step = self.sequence_engine.get_step_template(campaign.sequence_id, campaign.current_step)
            if next_step:
                # Find the delay for this step
                delay_days = 0
                for step in sequence_config.steps:
                    if step.step == campaign.current_step:
                        delay_days = step.delay_days
                        break
                campaign.next_action_at = datetime.now(timezone.utc) + timedelta(days=delay_days)
            else:
                # Sequence completed
                campaign.status = "COMPLETED"
                campaign.next_action_at = None

            # Log the outreach
            outreach_log = OutreachLog(
                business_id=lead_id,
                campaign_id=campaign_id,
                channel=channel.value,
                direction="OUTBOUND",
                subject=subject,
                content=html_content,
                status="SENT",
                sent_at=datetime.now(timezone.utc)
            )
            session.add(outreach_log)

            # Audit the send
            await AuditService.record(
                session,
                actor="system",
                action="outreach.send",
                entity_type="outreach_campaign",
                entity_id=campaign_id,
                payload={
                    "step": step_number,
                    "channel": channel.value,
                    "message_id": send_result_dict.get("message_id") if isinstance(send_result_dict, dict) else None,
                    "outbox_event_id": outbox_event_id
                }
            )

            await session.commit()

            # If sequence has more steps, schedule next one
            if campaign.status == "ACTIVE" and campaign.next_action_at:
                # Schedule next step via outbox
                new_event = OutboxEvent(
                    topic="outreach.send",
                    payload={
                        "campaign_id": campaign_id,
                        "lead_id": lead_id,
                        "step_number": campaign.current_step,
                        "channel": channel.value,
                        "personalization_data": enhanced_personalization
                    }
                )
                session.add(new_event)
                await session.commit()

            return True

        except Exception as e:
            # Send failed - log error and mark as failed
            outreach_log = OutreachLog(
                business_id=lead_id,
                campaign_id=campaign_id,
                channel=channel.value,
                direction="OUTBOUND",
                subject=subject,
                content=text_content,
                status="FAILED",
                sent_at=datetime.now(timezone.utc)
            )
            session.add(outreach_log)

            await AuditService.record(
                session,
                actor="system",
                action="outreach.send.failed",
                entity_type="outreach_campaign",
                entity_id=campaign_id,
                payload={"error": str(e), "step": step_number, "channel": channel.value, "outbox_event_id": outbox_event_id}
            )
            await session.commit()
            return True  # Retry on send failures

    async def handle_reply(
        self,
        session: AsyncSession,
        campaign: OutreachCampaign,
        reply_content: str,
        lead_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Classify and persist a reply, then apply its deterministic branch."""
        result = await self.reply_classifier.classify(reply_content, lead_context)
        message = (
            await session.execute(
                select(OutreachMessage)
                .where(OutreachMessage.campaign_id == campaign.id)
                .order_by(OutreachMessage.step_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if message is not None:
            message.replied_at = now
            message.reply_content = reply_content
            message.reply_classification = result.classification.value
            message.status = "REPLIED"

        if result.escalate:
            campaign.status = "PAUSED"
            fingerprint = hashlib.sha256(reply_content.encode()).hexdigest()
            session.add(
                ApprovalRequest(
                    action_type="outreach.reply_escalation",
                    entity_type="outreach_campaign",
                    entity_id=str(campaign.id),
                    context={
                        "classification": result.classification.value,
                        "confidence": result.confidence,
                        "reply_sha256": fingerprint,
                    },
                    thread_id=f"outreach-reply-{campaign.id}-{fingerprint[:12]}",
                    expires_at=now + timedelta(seconds=settings.approval_expiry_seconds),
                )
            )
        elif result.classification in {
            ReplyClassification.NOT_INTERESTED,
            ReplyClassification.UNSUBSCRIBE,
        }:
            campaign.status = (
                "OPTED_OUT"
                if result.classification == ReplyClassification.UNSUBSCRIBE
                else "COMPLETED"
            )
            business = await session.get(Business, campaign.lead_id)
            if business and business.email:
                await suppression.add(
                    session, email=business.email, reason=result.classification.value
                )
        elif result.classification == ReplyClassification.LATER:
            campaign.next_action_at = now + timedelta(days=30)
        elif result.classification == ReplyClassification.REFERRAL:
            campaign.status = "COMPLETED"
        elif result.classification == ReplyClassification.INTERESTED:
            campaign.status = "QUALIFIED"

        await AuditService.record(
            session,
            actor="system",
            action="outreach.reply.handled",
            entity_type="outreach_campaign",
            entity_id=str(campaign.id),
            payload={
                "classification": result.classification.value,
                "confidence": result.confidence,
                "source": result.source,
                "escalated": result.escalate,
            },
            correlation_id=str(campaign.id),
        )
        await session.commit()
        return {
            "classification": result.classification.value,
            "confidence": result.confidence,
            "escalated": result.escalate,
            "suggested_response": result.suggested_response,
        }

    async def handle_meeting_event(
        self,
        session: AsyncSession,
        campaign: OutreachCampaign,
        event: BookingEvent,
    ) -> OutreachMeeting:
        """Persist a booking transition and enqueue proposal generation on creation."""
        meeting = (
            await session.execute(
                select(OutreachMeeting).where(OutreachMeeting.booking_id == event.booking_id)
            )
        ).scalar_one_or_none()
        status = {
            BookingEventType.CREATED: "BOOKED",
            BookingEventType.CANCELLED: "CANCELLED",
            BookingEventType.RESCHEDULED: "RESCHEDULED",
        }[event.type]
        if meeting is None:
            meeting = OutreachMeeting(
                campaign_id=campaign.id,
                booking_id=event.booking_id,
                lead_email=event.lead_email,
                start_time=event.start_time,
                end_time=event.end_time,
                meeting_url=event.meeting_url,
                status=status,
            )
            session.add(meeting)
        else:
            meeting.start_time = event.start_time
            meeting.end_time = event.end_time
            meeting.meeting_url = event.meeting_url
            meeting.status = status
        if event.type == BookingEventType.CREATED:
            campaign.status = "MEETING_BOOKED"
            session.add(
                OutboxEvent(
                    topic="proposal.generate",
                    payload={"campaign_id": str(campaign.id), "lead_id": str(campaign.lead_id)},
                )
            )
        await AuditService.record(
            session,
            actor="system",
            action=f"outreach.meeting.{status.lower()}",
            entity_type="outreach_campaign",
            entity_id=str(campaign.id),
            payload={"booking_id": event.booking_id},
            correlation_id=str(campaign.id),
        )
        await session.commit()
        return meeting

    async def enqueue_follow_up(
        self, session: AsyncSession, campaign: OutreachCampaign, trigger_event: str
    ) -> bool:
        """Enqueue a configured event-based or time-based follow-up."""
        action = self.sequence_engine.compute_follow_up_action(campaign.sequence_id, trigger_event)
        if action is None or campaign.status != "ACTIVE":
            return False
        template, delay = action
        session.add(
            OutboxEvent(
                topic="outreach.send",
                next_run_at=datetime.now(timezone.utc) + delay,
                payload={
                    "campaign_id": str(campaign.id),
                    "lead_id": str(campaign.lead_id),
                    "step_number": campaign.current_step,
                    "channel": campaign.channel.lower(),
                    "template_override": template,
                    "personalization_data": {},
                },
            )
        )
        await AuditService.record(
            session,
            actor="system",
            action="outreach.follow_up.enqueued",
            entity_type="outreach_campaign",
            entity_id=str(campaign.id),
            payload={"trigger": trigger_event, "template": template},
            correlation_id=str(campaign.id),
        )
        await session.commit()
        return True


outreach_worker = OutreachWorker()
