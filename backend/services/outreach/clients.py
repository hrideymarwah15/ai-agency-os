"""Outreach channel clients for SendGrid and LinkedIn."""

from enum import Enum
from typing import Dict, List, Any, Optional
import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from backend.config import settings
from backend.services.audit import AuditService


class OutreachChannel(str, Enum):
    """Supported outreach channels."""
    EMAIL = "email"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"  # Placeholder for v2


class SendGridClient:
    """SendGrid email client with webhook parsing."""

    def __init__(self):
        self.api_key = settings.sendgrid_api_key
        self.from_email = settings.sendgrid_from_email
        self.base_url = "https://api.sendgrid.com/v3"
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        text_content: str,
        campaign_id: str,
        message_id: str,
    ) -> Dict[str, Any]:
        """Send email via SendGrid API.
        
        Returns:
            Dict with keys: sendgrid_message_id, status, status_code
        """
        personalizations = [{
            "to": [{"email": to_email, "name": to_name}],
            "dynamic_template_data": {
                "subject": subject,
                "preheader": subject[:100],  # Use subject as preheader
                "body": html_content,
            }
        }]
        
        # Using dynamic template approach - in practice, we'd use template_id
        # For now, we'll use mail send with content
        mail_data = {
            "personalizations": personalizations,
            "from": {"email": self.from_email},
            "subject": subject,
            "content": [
                {
                    "type": "text/plain",
                    "value": text_content
                },
                {
                    "type": "text/html",
                    "value": html_content
                }
            ]
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/mail/send",
                json=mail_data
            )
            response.raise_for_status()
            
            # Extract message ID from response headers
            sendgrid_message_id = response.headers.get("X-Message-Id", "")
            
            # Audit the send
            await AuditService.record(
                None,  # session - in practice would be passed
                actor="system",
                action="outreach.sent",
                entity_type="email",
                entity_id=to_email,
                payload={
                    "campaign_id": campaign_id,
                    "message_id": message_id,
                    "sendgrid_message_id": sendgrid_message_id,
                    "to_email": to_email,
                    "subject": subject,
                },
            )
            
            return {
                "sendgrid_message_id": sendgrid_message_id,
                "status": "sent",
                "status_code": response.status_code
            }
        except httpx.HTTPStatusError as e:
            # Audit the failure
            await AuditService.record(
                None,
                actor="system",
                action="outreach.send_failed",
                entity_type="email",
                entity_id=to_email,
                payload={
                    "campaign_id": campaign_id,
                    "message_id": message_id,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise
        except Exception as e:
            await AuditService.record(
                None,
                actor="system",
                action="outreach.send_failed",
                entity_type="email",
                entity_id=to_email,
                payload={
                    "campaign_id": campaign_id,
                    "message_id": message_id,
                    "error": str(e),
                },
            )
            raise

    def parse_webhook(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse SendGrid webhook payload into standardized events.
        
        SendGrid sends an array of event objects.
        Each event has: email, timestamp, sg_event_type, sg_message_id, etc.
        """
        events = []
        
        # Handle both single event and array of events
        if isinstance(payload, dict):
            payload = [payload]
        elif not isinstance(payload, list):
            return events
            
        for event in payload:
            sg_event_type = event.get("event", "")
            email = event.get("email", "")
            timestamp = event.get("timestamp", 0)
            
            # Map SendGrid event types to our standard types
            event_mapping = {
                "delivered": "delivered",
                "open": "opened",
                "click": "clicked",
                "bounce": "bounced",
                "spam_report": "spam_reported",
                "unsubscribe": "unsubscribed",
                "processed": "sent",  # Not a real status but indicates accepted by SG
                "dropped": "failed",
            }
            
            mapped_event = event_mapping.get(sg_event_type)
            if mapped_event and email:
                events.append({
                    "email": email,
                    "event": mapped_event,
                    "timestamp": timestamp,
                    "sg_message_id": event.get("sg_message_id", ""),
                    "sg_event_type": sg_event_type,
                    # Additional fields based on event type
                    "url": event.get("url"),  # for clicks
                    "reason": event.get("reason"),  # for bounces/drops
                })
                
        return events

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class LinkedInClient:
    """LinkedIn API client for official Marketing Developer Platform."""
    
    def __init__(self):
        # Note: LinkedIn credentials would be added to settings in config.py
        # For now, we'll note that these need to be configured
        self.client_id = getattr(settings, 'linkedin_client_id', '')
        self.client_secret = getattr(settings, 'linkedin_client_secret', '')
        self.redirect_uri = getattr(settings, 'linkedin_redirect_uri', '')
        self.access_token = None
        self.expires_at = 0
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _ensure_access_token(self):
        """Ensure we have a valid access token, refreshing if needed."""
        if self.access_token and time.time() < self.expires_at - 60:  # Refresh 1 min early
            return
            
        # In a real implementation, we would:
        # 1. Check if we have a valid token in cache/database
        # 2. If not, initiate OAuth flow (would require user interaction)
        # 3. For service-to-service, use client credentials grant (not typically available for LinkedIn)
        #
        # For this implementation, we'll note that proper OAuth flow is needed
        # and raise an informative error if credentials aren't configured
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "LinkedIn API credentials not configured. "
                "Please set linkedin_client_id and linkedin_client_secret in settings."
            )
        
        # Placeholder for actual OAuth token exchange
        # In reality, this would make a POST to LinkedIn's OAuth endpoint
        # For now, we'll simulate having a token
        self.access_token = "placeholder_access_token"
        self.expires_at = time.time() + 3600  # 1 hour expiry

    async def send_connection_request(
        self,
        profile_urn: str,
        message: str,
        campaign_id: str,
        message_id: str,
    ) -> Dict[str, Any]:
        """Send LinkedIn connection request.
        
        Note: LinkedIn's API does not allow automated connection requests
        as part of their Marketing Developer Platform. This would need to
        be done via manual approval or through Sales Navigator endpoints.
        
        For compliance with LinkedIn's Terms of Service, this implementation
        would require human-in-the-loop for connection requests.
        """
        await self._ensure_access_token()
        
        # This is a placeholder implementation
        # In reality, LinkedIn's API for connection requests is limited
        # and typically requires Sales Navigator or manual action
        
        # Audit the attempt
        await AuditService.record(
            None,
            actor="system",
            action="outreach.linkedin.connection_attempt",
            entity_type="linkedin_profile",
            entity_id=profile_urn,
            payload={
                "campaign_id": campaign_id,
                "message_id": message_id,
                "profile_urn": profile_urn,
                "message": message[:100],  # Truncate for logging
            },
        )
        
        # Return a placeholder response
        # In reality, this would return the actual invitation ID from LinkedIn
        return {
            "tracking_id": f"linkedin_conn_{int(time.time())}",
            "status": "sent",
            "note": "LinkedIn connection requests require manual approval per ToS"
        }

    async def send_message(
        self,
        conversation_urn: str,
        message: str,
        campaign_id: str,
        message_id: str,
    ) -> Dict[str, Any]:
        """Send LinkedIn message via messaging API.
        
        Requires: conversation_urn (from accepted connection)
        """
        await self._ensure_access_token()
        
        # Placeholder for actual LinkedIn message API call
        # Would POST to https://api.linkedin.com/v2/messaging/conversations/{conversation_urn}/messages
        
        # Audit the send
        await AuditService.record(
            None,
            actor="system",
            action="outreach.linkedin.message_sent",
            entity_type="linkedin_conversation",
            entity_id=conversation_urn,
            payload={
                "campaign_id": campaign_id,
                "message_id": message_id,
                "conversation_urn": conversation_urn,
                "message": message[:100],
            },
        )
        
        return {
            "tracking_id": f"linkedin_msg_{int(time.time())}",
            "status": "sent"
        }

    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status for LinkedIn API.
        
        LinkedIn uses various rate limits depending on the endpoint.
        For Marketing Developer Platform, typical limits are:
        - 100,000 calls per day
        - 100 calls per 10 seconds per user
        """
        # Placeholder implementation
        # In reality, we would check the X-RateLimit-Remaining headers
        # from LinkedIn API responses
        
        return {
            "remaining": 1000,  # placeholder
            "reset_at": int(time.time()) + 3600,
            "limit_daily": 100000,
            "limit_per_10_seconds": 100
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()