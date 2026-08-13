"""Strict Cal.com v2 client and signed webhook parser."""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from urllib.parse import quote

import httpx

from backend.config import settings


@dataclass(frozen=True)
class BookingResult:
    """Normalized successful Cal.com booking."""

    booking_id: str
    meeting_url: str | None
    start_time: datetime
    end_time: datetime | None
    ics_content: str | None = None


class BookingEventType(str, Enum):
    """Cal.com webhook booking transitions."""

    CREATED = "BOOKING_CREATED"
    CANCELLED = "BOOKING_CANCELLED"
    RESCHEDULED = "BOOKING_RESCHEDULED"


@dataclass(frozen=True)
class BookingEvent:
    """Verified and normalized Cal.com webhook event."""

    type: BookingEventType
    booking_id: str
    lead_email: str
    start_time: datetime
    end_time: datetime | None
    meeting_url: str | None = None


class MeetingScheduler:
    """Cal.com API v2 integration; missing credentials fail closed."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        username: str | None = None,
        event_type_id: str | None = None,
        webhook_secret: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = settings.cal_com_api_key if api_key is None else api_key
        self.username = settings.cal_com_username if username is None else username
        self.event_type_id = settings.cal_com_event_type_id if event_type_id is None else event_type_id
        self.webhook_secret = (
            settings.cal_com_webhook_secret if webhook_secret is None else webhook_secret
        )
        self.client = client or httpx.AsyncClient(timeout=30.0)
        self.base_url = "https://api.cal.com/v2"

    @property
    def configured(self) -> bool:
        """Return whether required API scheduling credentials exist."""
        return bool(self.api_key and self.username and self.event_type_id)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("CAL_COM_API_KEY is not configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "cal-api-version": "2024-08-13",
            "Content-Type": "application/json",
        }

    async def get_availability(
        self, event_type_id: str | None = None, days_ahead: int = 14
    ) -> list[dict[str, str]]:
        """Fetch UTC range slots for an event type."""
        event_id = event_type_id or self.event_type_id
        if not event_id:
            raise RuntimeError("CAL_COM_EVENT_TYPE_ID is not configured")
        now = datetime.now(UTC)
        response = await self.client.get(
            f"{self.base_url}/slots/available",
            headers=self._headers(),
            params={
                "eventTypeId": event_id,
                "start": now.isoformat(),
                "end": (now + timedelta(days=days_ahead)).isoformat(),
                "timeZone": "UTC",
                "format": "range",
            },
        )
        response.raise_for_status()
        slots = response.json().get("data", {}).get("slots", {})
        values = slots.values() if isinstance(slots, dict) else slots
        return [
            {"start_time": item["startTime"], "end_time": item["endTime"], "timezone": "UTC"}
            for item in values
        ]

    def create_booking_link(
        self,
        lead_email: str,
        lead_name: str,
        event_type_id: str | None = None,
        custom_fields: dict[str, str] | None = None,
    ) -> str:
        """Create a hosted Cal.com booking URL with encoded attendee fields."""
        event_id = event_type_id or self.event_type_id
        if not self.username or not event_id:
            raise RuntimeError("Cal.com username and event type are required")
        query = f"email={quote(lead_email)}&name={quote(lead_name)}"
        for key, value in (custom_fields or {}).items():
            query += f"&{quote(key)}={quote(value)}"
        return f"https://cal.com/{quote(self.username)}/{quote(str(event_id))}?{query}"

    async def create_booking_direct(
        self,
        start_time: datetime,
        lead_email: str,
        lead_name: str,
        event_type_id: str | None = None,
        custom_fields: dict[str, str] | None = None,
    ) -> BookingResult:
        """Create a confirmed booking through Cal.com API v2."""
        event_id = event_type_id or self.event_type_id
        if not event_id:
            raise RuntimeError("CAL_COM_EVENT_TYPE_ID is not configured")
        response = await self.client.post(
            f"{self.base_url}/bookings",
            headers=self._headers(),
            json={
                "eventTypeId": int(event_id) if str(event_id).isdigit() else event_id,
                "start": start_time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "attendee": {"name": lead_name, "email": lead_email, "timeZone": "UTC"},
                "metadata": custom_fields or {},
            },
        )
        response.raise_for_status()
        data = response.json().get("data", response.json())
        return BookingResult(
            booking_id=str(data.get("uid") or data.get("bookingId") or data.get("id")),
            meeting_url=data.get("meetingUrl") or data.get("location"),
            start_time=_parse_time(data.get("start") or data.get("startTime")),
            end_time=_parse_optional_time(data.get("end") or data.get("endTime")),
            ics_content=data.get("icsContent"),
        )

    async def cancel_booking(self, booking_id: str) -> bool:
        """Cancel a Cal.com booking by UID."""
        response = await self.client.post(
            f"{self.base_url}/bookings/{quote(booking_id)}/cancel",
            headers=self._headers(),
            json={"cancellationReason": "Cancelled by agency owner"},
        )
        response.raise_for_status()
        return True

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        """Verify Cal.com's SHA-256 HMAC over the exact request body."""
        if not self.webhook_secret or not signature:
            return False
        expected = hmac.new(self.webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        supplied = signature.removeprefix("sha256=")
        return hmac.compare_digest(expected, supplied)

    def handle_webhook(self, payload: dict[str, Any]) -> BookingEvent:
        """Normalize a previously verified Cal.com webhook payload."""
        event_type = BookingEventType(payload.get("triggerEvent") or payload.get("event"))
        data = payload.get("payload", payload.get("data", {}))
        booking = data.get("booking", data)
        attendees = booking.get("attendees") or data.get("attendees") or []
        email = attendees[0].get("email", "") if attendees else data.get("email", "")
        return BookingEvent(
            type=event_type,
            booking_id=str(booking.get("uid") or booking.get("id")),
            lead_email=email,
            start_time=_parse_time(booking.get("startTime") or booking.get("start")),
            end_time=_parse_optional_time(booking.get("endTime") or booking.get("end")),
            meeting_url=booking.get("meetingUrl") or booking.get("location"),
        )

    async def close(self) -> None:
        """Close the owned/injected HTTP client."""
        await self.client.aclose()


def _parse_time(value: str | None) -> datetime:
    if not value:
        raise ValueError("Cal.com payload is missing a required timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_optional_time(value: str | None) -> datetime | None:
    return _parse_time(value) if value else None


meeting_scheduler = MeetingScheduler()
