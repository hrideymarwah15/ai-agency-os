"""Source adapter contract for the discovery pipeline (LEAD-04/05, D-21/D-23/D-24).

Each source declares its compliance posture (api_hosts for robots exemption,
requires_keys for key-gated sources) and yields SourceCandidate streams; per-item
failures become ParseError with a bounded reason bucket (LEAD-05 rejection
metrics) and are counted via SourceStatCollector — never swallowed into
candidates.
"""

import enum
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, ClassVar
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.tools.http_client import CompliantHTTPClient


class RejectReason(str, enum.Enum):
    """Bounded rejection buckets for LEAD-05 per-source metrics."""

    MISSING_NAME = "missing_name"
    MISSING_WEBSITE = "missing_website"
    MALFORMED = "malformed"
    TOO_SHORT = "too_short"
    BLOCKED = "blocked"  # robots denied / HTTP 403 / excluded platform
    DISABLED = "disabled"  # source not configured (D-21)


class ParseError(RuntimeError):
    """Raised when a source item fails to parse — mirrors RobotsDeniedError."""

    def __init__(self, reason: RejectReason, *, item_id: str | None = None) -> None:
        super().__init__(f"{reason.value}:{item_id or ''}")
        self.reason = reason
        self.item_id = item_id


@dataclass
class SourceStatCollector:
    """Per-source counters + rejection buckets (LEAD-05; mirrors DiscoveryRunSourceStat)."""

    source_id: str
    requests_made: int = 0
    found: int = 0
    parsed_ok: int = 0
    rejected: int = 0
    rejection_buckets: dict[str, int] = field(default_factory=dict)

    def record_request(self) -> None:
        """Count one outbound request through the compliant door."""
        self.requests_made += 1

    def record_found(self) -> None:
        """Count one raw item seen."""
        self.found += 1

    def record_parsed(self) -> None:
        """Count one accepted candidate."""
        self.parsed_ok += 1

    def reject(self, reason: RejectReason, *, item_id: str | None = None) -> None:
        """Count one rejected item into its bounded bucket."""
        self.rejected += 1
        self.rejection_buckets[reason.value] = self.rejection_buckets.get(reason.value, 0) + 1
        if item_id is not None:
            logger.debug(
                "discovery rejection source={} reason={} item_id={}",
                self.source_id,
                reason.value,
                item_id,
            )


@dataclass
class RunContext:
    """Per-run context handed to every adapter (the D-15 door is already api_hosts-aware)."""

    run_id: UUID
    correlation_id: str
    client: CompliantHTTPClient
    session: AsyncSession
    stat: SourceStatCollector


@dataclass
class SourceCandidate:
    """One normalized candidate — the idempotency key is (source_id, source_item_id)."""

    source_id: str
    source_item_id: str  # idempotency key: unique per source item
    raw: dict[str, Any]  # sanitized + size-capped raw payload (lineage, D-24)
    text: str  # sanitized text (CMP-06: inert, data-only)
    normalized: dict[str, Any]  # unified schema subset (SPEC-002 §8.2)


class SourceAdapter(ABC):
    """Abstract source adapter — one class per external source, live and mock."""

    source_id: ClassVar[str]
    display_name: ClassVar[str]
    short_name: ClassVar[str]
    api_hosts: ClassVar[frozenset[str]] = frozenset()  # robots-exempt API hosts (D-31)
    requires_keys: ClassVar[bool] = False  # Yelp/Google: key-gated (D-21)

    @abstractmethod
    def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
        """Yield candidates for one run; per-item failures are counted via ctx.stat.

        Implementations are async generators — never an `async def` returning a
        coroutine (mypy: async-generator functions type as AsyncIterator, not
        Coroutine[..., AsyncIterator[SourceCandidate]]).
        """
        ...
