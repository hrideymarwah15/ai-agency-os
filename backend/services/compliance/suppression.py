"""Suppression list — add/lookup against suppression_entries (CMP-04)."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import SuppressionEntry


def _normalize(email: str) -> str:
    """Trim whitespace and lowercase — email identity is case-insensitive."""
    return email.strip().lower()


async def add(session: AsyncSession, *, email: str, reason: str) -> None:
    """Insert a suppression entry (idempotent — ON CONFLICT DO NOTHING)."""
    stmt = (
        insert(SuppressionEntry)
        .values(email=_normalize(email), reason=reason)
        .on_conflict_do_nothing(index_elements=["email"])
    )
    await session.execute(stmt)
    await session.commit()


async def is_suppressed(session: AsyncSession, email: str) -> bool:
    """True when the normalized email has a suppression entry."""
    result = await session.execute(
        select(SuppressionEntry).where(SuppressionEntry.email == _normalize(email))
    )
    return result.scalar_one_or_none() is not None
