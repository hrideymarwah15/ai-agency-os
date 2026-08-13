"""Tests for outreach channel clients."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from backend.services.outreach.clients import SendGridClient, LinkedInClient, OutreachChannel
from backend.services.audit import AuditService
from backend.config import settings


class TestOutreachChannel:
    """Tests for OutreachChannel enum."""

    def test_outreach_channel_values(self):
        """Test that OutreachChannel has expected values."""
        assert OutreachChannel.EMAIL == "email"
        assert OutreachChannel.LINKEDIN == "linkedin"
        assert OutreachChannel.WHATSAPP == "whatsapp"


class TestSendGridClient:
    """Tests for SendGridClient."""

    @pytest.fixture
    def sendgrid_client(self):
        """Create a SendGridClient instance."""
        return SendGridClient()

    @pytest.mark.asyncio
    async def test_send_email_success(self, sendgrid_client):
        """Test successful email sending."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {
            "id": "test-message-id"
        }

        with patch.object(sendgrid_client, 'client') as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await sendgrid_client.send_email(
                to_email="test@example.com",
                to_name="Test User",
                subject="Test Subject",
                html_content="<p>Test HTML</p>",
                text_content="Test Text",
                campaign_id=str(uuid4()),
                message_id=str(uuid4())
            )

            assert result["status"] == "success"
            assert result["sendgrid_message_id"] == "test-message-id"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_failure(self, sendgrid_client):
        """Test email sending failure."""
        # Mock the HTTP client to return an error
        mock_response = MagicMock()
        mock_response.status_code = 400

        with patch.object(sendgrid_client, 'client') as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(Exception):  # Should raise HTTPException or similar
                await sendgrid_client.send_email(
                    to_email="test@example.com",
                    to_name="Test User",
                    subject="Test Subject",
                    html_content="<p>Test HTML</p>",
                    text_content="Test Text",
                    campaign_id=str(uuid4()),
                    message_id=str(uuid4())
                )

    @pytest.mark.asyncio
    async def test_parse_webhook(self, sendgrid_client):
        """Test parsing SendGrid webhook payload."""
        webhook_payload = [
            {
                "email": "test@example.com",
                "timestamp": 1234567890,
                "smtp-id": "<test@example.com>",
                "event": "delivered"
            },
            {
                "email": "test@example.com",
                "timestamp": 1234567895,
                "smtp-id": "<test@example.com>",
                "event": "open"
            }
        ]

        # Mock the signature verification (not implementing full signature check for unit test)
        with patch.object(sendgrid_client, '_verify_signature', return_value=True):
            events = await sendgrid_client.parse_webhook(webhook_payload)

            assert len(events) == 2
            assert events[0]["event"] == "delivered"
            assert events[1]["event"] == "open"


class TestLinkedInClient:
    """Tests for LinkedInClient."""

    @pytest.fixture
    def linkedin_client(self):
        """Create a LinkedInClient instance."""
        return LinkedInClient()

    @pytest.mark.asyncio
    async def test_send_connection_request(self, linkedin_client):
        """Test sending a LinkedIn connection request."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "test-connection-id"
        }

        with patch.object(linkedin_client, 'client') as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await linkedin_client.send_connection_request(
                profile_urn="urn:li:person:test",
                message="Hello, I'd like to connect",
                campaign_id=str(uuid4()),
                message_id=str(uuid4())
            )

            assert result["status"] == "success"
            assert result["tracking_id"] == "test-connection-id"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message(self, linkedin_client):
        """Test sending a LinkedIn message."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "test-message-id"
        }

        with patch.object(linkedin_client, 'client') as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await linkedin_client.send_message(
                conversation_urn="urn:li:messengerGroup:test",
                message="Hello, this is a test message",
                campaign_id=str(uuid4()),
                message_id=str(uuid4())
            )

            assert result["status"] == "success"
            assert result["tracking_id"] == "test-message-id"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self, linkedin_client):
        """Test getting LinkedIn rate limit status."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "remaining": 450,
            "reset_time": 1234567890
        }

        with patch.object(linkedin_client, 'client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            status = await linkedin_client.get_rate_limit_status()

            assert status["remaining"] == 450
            assert status["reset_at"] == 1234567890
            mock_client.get.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])