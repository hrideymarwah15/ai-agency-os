"""Shared audit contracts — status enum refs, run context, check envelopes.

Mirrors services/discovery/base.py's role: AuditStatus lives in database.py
(D-35); this module carries the per-audit AuditContext dataclass handed to
the static/rendered/link passes and the check-result envelope shapes the
runner stores (RESEARCH §Pattern 5).
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.tools.http_client import CompliantHTTPClient


@dataclass
class AuditContext:
    """One audit run's per-pass context (runner builds and threads this)."""

    audit_id: UUID
    business_id: UUID
    website_url: str
    client: CompliantHTTPClient
    session: AsyncSession
    broken_links: list[dict[str, Any]] = field(default_factory=list)
