"""Cal.com v2 client and webhook security tests."""

import hashlib
import hmac
import json
from datetime import UTC, datetime

import httpx
import pytest

from backend.services.outreach.meeting_scheduler import BookingEventType, MeetingScheduler


@pytest.mark.anyio
async def test_direct_booking_v2_request():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["cal-api-version"] == "2024-08-13"
        return httpx.Response(
            201,
            json={
                "data": {
                    "uid": "book-1",
                    "start": "2026-08-20T10:00:00Z",
                    "end": "2026-08-20T10:30:00Z",
                    "meetingUrl": "https://meet.example/1",
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    scheduler = MeetingScheduler(api_key="cal_test", username="owner", event_type_id="42", client=client)
    result = await scheduler.create_booking_direct(
        datetime(2026, 8, 20, 10, tzinfo=UTC), "lead@example.com", "Lead"
    )
    assert result.booking_id == "book-1"
    await client.aclose()


def test_webhook_signature_and_parse():
    scheduler = MeetingScheduler(webhook_secret="secret")
    payload = {
        "triggerEvent": "BOOKING_CREATED",
        "payload": {
            "uid": "book-1",
            "startTime": "2026-08-20T10:00:00Z",
            "endTime": "2026-08-20T10:30:00Z",
            "attendees": [{"email": "lead@example.com"}],
        },
    }
    raw = json.dumps(payload).encode()
    signature = hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
    assert scheduler.verify_webhook(raw, signature)
    event = scheduler.handle_webhook(payload)
    assert event.type == BookingEventType.CREATED
    assert event.lead_email == "lead@example.com"


def test_missing_webhook_secret_fails_closed():
    assert MeetingScheduler(webhook_secret="").verify_webhook(b"{}", "anything") is False
