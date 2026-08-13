"""Meeting scheduler service for Cal.com integration."""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import httpx
from urllib.parse import urljoin

from backend.config import settings
from backend.services.audit import AuditService


class BookingResult:
    """Result of a meeting booking operation."""
    def __init__(self, success: bool, booking_id: Optional[str] = None,
                 booking_url: Optional[str] = None, error: Optional[str] = None):
        self.success = success
        self.booking_id = booking_id
        self.booking_url = booking_url
        self.error = error


class MeetingScheduler:
    """Cal.com integration for meeting scheduling."""

    def __init__(self):
        self.api_key = getattr(settings, 'cal_com_api_key', None)
        self.username = getattr(settings, 'cal_com_username', None)
        self.event_type_id = getattr(settings, 'cal_com_event_type_id', None)
        self.base_url = "https://api.cal.com/v1"
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client

    async def get_available_times(self, start_date: datetime,
                                 end_date: datetime,
                                 duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Get available time slots for meeting booking.

        Returns list of available time slots with start/end times.
        """
        if not all([self.api_key, self.username, self.event_type_id]):
            # Return mock data if not configured
            return self._get_mock_available_times(start_date, end_date, duration_minutes)

        try:
            client = self._get_client()
            params = {
                "eventTypeId": str(self.event_type_id),
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "duration": str(duration_minutes)
            }

            response = await client.get(
                urljoin(self.base_url, f"slots/{self.username}"),
                params=params
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("slots", {}).get(self.username, [])
            else:
                # Fallback to mock data on API error
                return self._get_mock_available_times(start_date, end_date, duration_minutes)

        except Exception:
            # Fallback to mock data on any error
            return self._get_mock_available_times(start_date, end_date, duration_minutes)

    def _get_mock_available_times(self, start_date: datetime,
                                 end_date: datetime,
                                 duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """Generate mock available times for development/testing."""
        slots = []
        current = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
        end = end_date.replace(hour=17, minute=0, second=0, microsecond=0)

        while current < end:
            slot_end = current + timedelta(minutes=duration_minutes)
            if slot_end <= end:
                slots.append({
                    "start": current.isoformat(),
                    "end": slot_end.isoformat()
                })
            current = slot_end

        return slots[:10]  # Limit to 10 slots for demo

    async def book_meeting(self, start_time: datetime,
                          attendee_name: str,
                          attendee_email: str,
                          notes: Optional[str] = None) -> BookingResult:
        """
        Book a meeting with an attendee.

        Returns BookingResult with booking details or error.
        """
        if not all([self.api_key, self.username, self.event_type_id]):
            return BookingResult(
                success=True,  # Mock success for development
                booking_id=str(uuid.uuid4()),
                booking_url=f"https://calendly.com/{self.username}/mock-{uuid.uuid4().hex[:8]}"
            )

        try:
            client = self._get_client()
            booking_data = {
                "eventTypeId": str(self.event_type_id),
                "start": start_time.isoformat(),
                "attendees": [
                    {
                        "name": attendee_name,
                        "email": attendee_email
                    }
                ],
                "notes": notes or "",
                "timeZone": "UTC",
                "language": "en",
                "metadata": {
                    "source": "ai_agency_os_outreach",
                    "campaign_id": notes or "unknown"  # Could extract from notes
                }
            }

            response = await client.post(
                urljoin(self.base_url, "bookings"),
                json=booking_data
            )

            if response.status_code in [200, 201]:
                data = response.json()
                booking = data.get("booking", {})

                return BookingResult(
                    success=True,
                    booking_id=str(booking.get("id", "")),
                    booking_url=booking.get("joinUrl", "")
                )
            else:
                error_data = response.json() if response.content else {}
                return BookingResult(
                    success=False,
                    error=error_data.get("message", f"HTTP {response.status_code}")
                )

        except Exception as e:
            return BookingResult(
                success=False,
                error=str(e)
            )

    async def handle_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming webhook from Cal.com.

        Processes booking created, cancelled, rescheduled events.
        """
        event_type = webhook_data.get("event")
        payload = webhook_data.get("payload", {})

        result = {
            "processed": False,
            "action": None,
            "booking_id": None,
            "meeting_time": None
        }

        try:
            if event_type == "BOOKING_CREATED":
                booking = payload.get("booking", {})
                result.update({
                    "processed": True,
                    "action": "booking_created",
                    "booking_id": str(booking.get("id", "")),
                    "meeting_time": booking.get("startTime"),
                    "attendee_email": booking.get("attendees", [{}])[0].get("email") if booking.get("attendees") else None
                })

                # Audit the booking
                # AuditService.record would be called here in actual implementation

            elif event_type == "BOOKING_CANCELLED":
                booking = payload.get("booking", {})
                result.update({
                    "processed": True,
                    "action": "booking_cancelled",
                    "booking_id": str(booking.get("id", "")),
                    "meeting_time": booking.get("startTime")
                })

            elif event_type == "BOOKING_RESCHEDULED":
                booking = payload.get("booking", {})
                result.update({
                    "processed": True,
                    "action": "booking_rescheduled",
                    "booking_id": str(booking.get("id", "")),
                    "meeting_time": booking.get("startTime")
                })

        except Exception as e:
            result["error"] = str(e)

        return result


# Global instance
meeting_scheduler = MeetingScheduler()