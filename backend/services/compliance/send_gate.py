"""Send gate: consent → suppression → volume cap → per-channel rate limit → unsubscribe footer (CMP-03/04)."""

from typing import Any
from uuid import UUID

from itsdangerous import TimestampSigner, BadSignature, SignatureExpired
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.services.audit import AuditService
from backend.services.compliance.consent import has_consent
from backend.services.compliance.rate_limit import DomainTokenBucket
from backend.services.compliance.suppression import is_suppressed
from backend.services.outreach.clients import OutreachChannel


class SendGateResult:
    """Result of send gate evaluation."""
    def __init__(self, allowed: bool, reason: str = "", unsubscribe_footer: str = ""):
        self.allowed = allowed
        self.reason = reason
        self.unsubscribe_footer = unsubscribe_footer


async def send_gate(
    session: AsyncSession,
    *,
    lead_id: UUID,
    channel: OutreachChannel,
    content: str,
    email: str
) -> SendGateResult:
    """
    Return SendGateResult when all checks pass.

    Checks in order:
    1. ConsentRecord exists for lead email (lawful_basis in ['legitimate_interest', 'consent'])
    2. Email not in SuppressionEntry
    3. Daily volume cap not exceeded (OutreachSpend for today < max_daily_sends_per_channel)
    4. Per-channel rate limit (token bucket from compliance/rate_limit.py)

    If allowed: returns unsubscribe_footer HTML with one-click link (signed token)
    If denied: logs to audit_logs with action='outreach.blocked', reason
    """
    # Check 1: Consent
    if not await has_consent(session, email):
        await _block_and_log(session, lead_id, channel, "consent_required", email)
        return SendGateResult(False, "consent_required")

    # Check 2: Suppression list
    if await is_suppressed(session, email):
        await _block_and_log(session, lead_id, channel, "suppressed", email)
        return SendGateResult(False, "suppressed")

    # Check 3: Daily volume cap via OutreachSpend table
    from datetime import date
    from sqlalchemy import select, func
    from backend.database import OutreachSpend

    today = date.today()
    result = await session.execute(
        select(OutreachSpend.sent_count)
        .where(
            OutreachSpend.spend_date == today,
            OutreachSpend.channel == channel.value
        )
    )
    sent_today = result.scalar_one_or_none() or 0

    max_daily = settings.global_settings.get("max_daily_sends_per_channel", 100)
    if sent_today >= max_daily:
        await _block_and_log(session, lead_id, channel, "daily_cap_exceeded", email)
        return SendGateResult(False, "daily_cap_exceeded")

    # Check 4: Per-channel rate limit (token bucket)
    rate_limiter = DomainTokenBucket(
        capacity=settings.global_settings.get(f"rate_limit_{channel.value}_burst", 10),
        refill_per_sec=settings.global_settings.get(f"rate_limit_{channel.value}_per_second", 1.0)
    )

    if not rate_limiter.try_acquire(channel.value):
        await _block_and_log(session, lead_id, channel, "rate_limit_exceeded", email)
        return SendGateResult(False, "rate_limit_exceeded")

    # All checks passed - generate unsubscribe footer
    unsubscribe_footer = _generate_unsubscribe_footer(lead_id, channel)

    return SendGateResult(True, "", unsubscribe_footer)


async def _block_and_log(
    session: AsyncSession,
    lead_id: UUID,
    channel: OutreachChannel,
    reason: str,
    email: str
) -> None:
    """Log a blocked send attempt to audit log."""
    await AuditService.record(
        session,
        actor="system",
        action="outreach.blocked",
        entity_type="lead",
        entity_id=str(lead_id),
        payload={
            "reason": reason,
            "channel": channel.value,
            "email": email
        }
    )
    await session.commit()


def _generate_unsubscribe_footer(lead_id: UUID, channel: OutreachChannel) -> str:
    """Generate HTML unsubscribe footer with signed token."""
    # Create token that expires in 7 days
    signer = TimestampSigner(settings.secret_key)
    token_data = f"{lead_id}:{channel.value}"
    token = signer.sign(token_data).decode('utf-8')

    # Get unsubscribe link template from config
    unsubscribe_template = settings.global_settings.get(
        "unsubscribe_link_template",
        "https://yourapi.com/api/v1/outreach/unsubscribe?token={{unsubscribe_token}}"
    )

    unsubscribe_link = unsubscribe_template.replace("{{unsubscribe_token}}", token)

    return f"""
    <div style="margin-top: 20px; padding-top: 10px; border-top: 1px solid #eee; font-size: 12px; color: #666;">
        This email was sent to you because you are a potential business partner.
        If you wish to not receive future emails, you can <a href="{unsubscribe_link}">unsubscribe here</a>.
    </div>
    """.strip()