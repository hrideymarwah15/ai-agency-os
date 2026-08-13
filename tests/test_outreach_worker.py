"""Focused outreach worker contract tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.database import OutreachCampaign, OutreachMeeting, OutboxEvent
from backend.services.outreach.meeting_scheduler import BookingEvent, BookingEventType
from backend.services.outreach.worker import OutreachWorker


def test_worker_initialization():
    worker = OutreachWorker()
    assert worker.sequence_engine is not None
    assert worker.reply_classifier is not None
    assert worker.meeting_scheduler is not None


@pytest.mark.anyio
async def test_worker_start_stop():
    worker = OutreachWorker()
    worker._process_one = AsyncMock(return_value=False)
    await worker.start()
    assert worker._running is True
    await worker.stop()
    assert worker._running is False


@pytest.mark.anyio
async def test_invalid_outbox_payload_is_rejected():
    worker = OutreachWorker()
    session = MagicMock()
    session.commit = AsyncMock()
    event = OutboxEvent(id=uuid4(), topic="outreach.send", payload={})
    assert await worker._process_outreach_send_event(session, event) is False


@pytest.mark.anyio
async def test_meeting_event_updates_existing_record():
    worker = OutreachWorker()
    session = MagicMock()
    meeting = OutreachMeeting(
        campaign_id=uuid4(),
        booking_id="book-1",
        lead_email="lead@example.com",
        start_time=datetime(2026, 8, 20, 10, tzinfo=UTC),
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = meeting
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    campaign = OutreachCampaign(
        id=meeting.campaign_id,
        lead_id=uuid4(),
        sequence_id="cold_email_5touch",
        channel="email",
    )
    event = BookingEvent(
        type=BookingEventType.CANCELLED,
        booking_id="book-1",
        lead_email="lead@example.com",
        start_time=datetime(2026, 8, 21, 10, tzinfo=UTC),
        end_time=None,
    )
    updated = await worker.handle_meeting_event(session, campaign, event)
    assert updated.status == "CANCELLED"
    assert updated.start_time == event.start_time
