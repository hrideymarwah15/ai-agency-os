"""Outreach orchestration unit-integration tests with fake async sessions."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.database import OutreachCampaign
from backend.services.outreach.meeting_scheduler import BookingEvent, BookingEventType
from backend.services.outreach.worker import OutreachWorker


@pytest.mark.anyio
async def test_meeting_created_enqueues_proposal():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    campaign = OutreachCampaign(
        id=uuid4(), lead_id=uuid4(), sequence_id="cold_email_5touch", channel="email"
    )
    event = BookingEvent(
        type=BookingEventType.CREATED,
        booking_id="book-1",
        lead_email="lead@example.com",
        start_time=datetime(2026, 8, 20, 10, tzinfo=UTC),
        end_time=datetime(2026, 8, 20, 10, 30, tzinfo=UTC),
    )
    await OutreachWorker().handle_meeting_event(session, campaign, event)
    added = [call.args[0] for call in session.add.call_args_list]
    assert any(getattr(item, "topic", None) == "proposal.generate" for item in added)
    assert campaign.status == "MEETING_BOOKED"


@pytest.mark.anyio
async def test_follow_up_trigger_enqueues_send():
    session = MagicMock()
    session.commit = AsyncMock()
    campaign = OutreachCampaign(
        id=uuid4(),
        lead_id=uuid4(),
        sequence_id="cold_email_5touch",
        channel="email",
        status="ACTIVE",
        current_step=1,
    )
    enqueued = await OutreachWorker().enqueue_follow_up(session, campaign, "email_open")
    assert enqueued is True
    added = [call.args[0] for call in session.add.call_args_list]
    assert any(getattr(item, "topic", None) == "outreach.send" for item in added)
