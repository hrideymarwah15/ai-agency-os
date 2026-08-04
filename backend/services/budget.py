"""Atomic budget counters — FND-06/D-11: hard caps enforced with guarded UPDATEs.

The invariant: a single atomic statement whose EVERY write path is guarded —
`INSERT ... SELECT ... WHERE cost <= cap` (first-ever call) and
`ON CONFLICT DO UPDATE ... WHERE existing + cost <= cap` (subsequent calls).
No read-then-write anywhere, so concurrent reservations can never overspend
(T-04-01). Zero rows returned ⇒ hard block: audit event + BudgetExceededError,
before the provider is ever contacted (T-04-02).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import LLMSpend, OutreachSpend
from backend.services.audit import AuditService

_LLM_RESERVE_SQL = """
INSERT INTO llm_spend (id, provider, model, spend_date, cost_cents, calls, created_at)
SELECT gen_random_uuid(), :provider, :model, :today, CAST(:cost_cents AS integer), 1, NOW()
WHERE CAST(:cost_cents AS integer) <= :cap
ON CONFLICT (provider, model, spend_date)
DO UPDATE SET cost_cents = llm_spend.cost_cents + CAST(:cost_cents AS integer),
              calls = llm_spend.calls + 1
WHERE llm_spend.cost_cents + CAST(:cost_cents AS integer) <= :cap
RETURNING id
"""

_OUTREACH_RESERVE_SQL = """
INSERT INTO outreach_spend (id, spend_date, channel, sent_count, created_at)
SELECT gen_random_uuid(), :today, :channel, 1, NOW()
WHERE 1 <= :cap
ON CONFLICT (spend_date, channel)
DO UPDATE SET sent_count = outreach_spend.sent_count + 1
WHERE outreach_spend.sent_count + 1 <= :cap
RETURNING id
"""


class BudgetExceededError(Exception):
    """Raised when a reservation would exceed its cap (hard block, D-11)."""

    def __init__(self, *, kind: str, key: str, cap: int, requested: int) -> None:
        self.kind = kind
        self.key = key
        self.cap = cap
        self.requested = requested
        super().__init__(f"{kind} budget exceeded for {key}: {requested} requested, cap is {cap}")


async def reserve_llm(session: AsyncSession, *, provider: str, model: str, cost_cents: int) -> None:
    """Atomically reserve cost_cents against the provider's daily cap (hard block)."""
    cap = int(getattr(settings, f"llm_daily_budget_usd_{provider}") * 100)
    result = await session.execute(
        text(_LLM_RESERVE_SQL),
        {
            "provider": provider,
            "model": model,
            "today": datetime.now(UTC).date(),
            "cost_cents": cost_cents,
            "cap": cap,
        },
    )
    # NOTE: AsyncSession.execute returns ChunkedIteratorResult (no .rowcount)
    # for DML..RETURNING — a returned row IS the success signal.
    if result.scalar_one_or_none() is None:
        await _audit_block(
            session,
            entity_type="llm_spend",
            entity_id=provider,
            payload={
                "provider": provider,
                "model": model,
                "cost_cents": cost_cents,
                "cap_cents": cap,
            },
        )
        raise BudgetExceededError(kind="llm", key=provider, cap=cap, requested=cost_cents)
    await session.commit()


async def reserve_outreach(session: AsyncSession, *, channel: str) -> None:
    """Atomically reserve one send against the daily outreach volume cap."""
    cap = settings.daily_outreach_limit
    result = await session.execute(
        text(_OUTREACH_RESERVE_SQL),
        {"today": datetime.now(UTC).date(), "channel": channel, "cap": cap},
    )
    if result.scalar_one_or_none() is None:
        await _audit_block(
            session,
            entity_type="outreach_spend",
            entity_id=channel,
            payload={"channel": channel, "sent_count": 1, "cap": cap},
        )
        raise BudgetExceededError(kind="outreach", key=channel, cap=cap, requested=1)
    await session.commit()


async def prune_spend_rows(session: AsyncSession, *, retention_days: int = 30) -> None:
    """Delete spend rows older than retention_days (date-keyed counters self-reset daily)."""
    cutoff = datetime.now(UTC).date() - timedelta(days=retention_days)
    await session.execute(delete(LLMSpend).where(LLMSpend.spend_date < cutoff))
    await session.execute(delete(OutreachSpend).where(OutreachSpend.spend_date < cutoff))
    await session.commit()


async def _audit_block(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
) -> None:
    """Persist the budget_blocked audit event (T-04-05: actor=system, immutable trail)."""
    await AuditService.record(
        session,
        actor="system",
        action="budget_blocked",
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        correlation_id=str(uuid4()),
    )
    await session.commit()
