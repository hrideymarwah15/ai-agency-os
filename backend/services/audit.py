"""Append-only audit service — the single write path for audit_logs (D-07)."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AuditLog


class AuditService:
    """Append-only audit write path. No update or delete methods exist by design."""

    @staticmethod
    async def record(
        session: AsyncSession,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, Any],
        correlation_id: str,
    ) -> None:
        """Insert one audit row (INSERT only — immutability enforced at the DB too)."""
        session.add(
            AuditLog(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload,
                correlation_id=correlation_id,
            )
        )

    @staticmethod
    async def list_recent(session: AsyncSession, limit: int = 50) -> Sequence[AuditLog]:
        """Return the newest audit entries first."""
        result = await session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return result.scalars().all()
