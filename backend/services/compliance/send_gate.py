"""The single send door (D-15 #2): consent → suppression → cap → address (CMP-03/04).

Phase 3's send infrastructure MUST call check_send before every send — this
choke point is what exists now (D-14). Every block is audited as send_blocked
with its reason (T-05-03); the daily cap uses the atomic reserve_outreach
counter from plan 04, so concurrent sends can never overshoot.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.services.audit import AuditService
from backend.services.budget import BudgetExceededError, reserve_outreach
from backend.services.compliance.consent import has_consent
from backend.services.compliance.suppression import is_suppressed


async def check_send(session: AsyncSession, *, email: str, channel: str) -> dict[str, Any]:
    """Return {"allowed": True} only when consent, suppression, cap, and address all pass."""
    if not await has_consent(session, email):
        return await _block(session, email, channel, "consent_required")
    if await is_suppressed(session, email):
        return await _block(session, email, channel, "suppressed")
    if not settings.agency_address:
        return await _block(session, email, channel, "address_required")
    try:
        await reserve_outreach(session, channel=channel)
    except BudgetExceededError:
        return await _block(session, email, channel, "daily_cap_exceeded")
    return {"allowed": True}


async def _block(session: AsyncSession, email: str, channel: str, reason: str) -> dict[str, Any]:
    """Audit the blocked send and return the deny envelope."""
    await AuditService.record(
        session,
        actor="system",
        action="send_blocked",
        entity_type="email",
        entity_id=email,
        payload={"reason": reason, "channel": channel},
    )
    await session.commit()
    return {"allowed": False, "reason": reason}
