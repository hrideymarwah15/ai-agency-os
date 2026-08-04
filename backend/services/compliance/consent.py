"""Consent records — lawful basis, source, ip, user_agent (CMP-04)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import ConsentRecord


def _normalize(email: str) -> str:
    """Trim whitespace and lowercase — email identity is case-insensitive."""
    return email.strip().lower()


async def record_consent(
    session: AsyncSession,
    *,
    email: str,
    lawful_basis: str,
    source: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record consent with its provenance (basis, source, ip, user_agent)."""
    session.add(
        ConsentRecord(
            email=_normalize(email),
            lawful_basis=lawful_basis,
            source=source,
            ip=ip,
            user_agent=user_agent,
        )
    )
    await session.commit()


async def has_consent(session: AsyncSession, email: str) -> bool:
    """True when at least one consent record exists for the normalized email."""
    result = await session.execute(
        select(ConsentRecord.id).where(ConsentRecord.email == _normalize(email)).limit(1)
    )
    return result.scalar_one_or_none() is not None
