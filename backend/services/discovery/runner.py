"""Discovery run executor (T07) — one run, one transaction (Pitfall 5).

For each enabled source (registry order): collect candidates through the
compliant door, dedup/enrich, and persist per-source stats and run totals in
the SAME transaction as the candidate inserts. Source failures never retry
harder (Pitfall 4): a robots denial or HTTP 429/403 blocks that source and
stops it for the run; per-item parse failures land in rejection buckets.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend import database
from backend.config import settings
from backend.database import (
    DiscoveryRun,
    DiscoveryRunSourceStat,
    RunStatus,
    SourceRunStatus,
)
from backend.services.audit import AuditService
from backend.services.discovery import registry
from backend.services.discovery.base import (
    ParseError,
    RejectReason,
    RunContext,
    SourceAdapter,
    SourceStatCollector,
)
from backend.services.discovery.dedup import ingest_candidate
from backend.services.discovery.enricher import enrich_homepage
from backend.services.discovery.normalize import (
    normalize_domain,
    normalize_email,
    normalize_name,
    normalize_phone,
)
from backend.services.discovery.sanitize import strip_html_to_text
from backend.tools.http_client import (
    CompliantHTTPClient,
    RobotsDeniedError,
    build_compliant_client,
)

# Builds the compliant client for one source (test seam: injected in tests).
ClientFactory = Callable[[SourceAdapter], CompliantHTTPClient]


def _default_client_factory(session: AsyncSession) -> ClientFactory:
    """Production factory: shared token bucket, api_hosts robots exemption (D-31)."""

    def build(adapter: SourceAdapter) -> CompliantHTTPClient:
        return build_compliant_client(api_hosts=adapter.api_hosts, session=session)

    return build


def _renormalize(normalized: dict[str, Any]) -> dict[str, Any]:
    """Defensive re-normalization of the four dedup keys (idempotent, T07)."""
    return {
        **normalized,
        "name": normalize_name(normalized.get("name")),
        "domain": normalize_domain(normalized.get("website")),
        "email": normalize_email(normalized.get("email")),
        "phone": normalize_phone(normalized.get("phone")),
    }


async def _audit_exclusion(ctx: RunContext, reason: str) -> None:
    """Record a source_excluded audit (LEAD-04) — blocked sources are visible."""
    await AuditService.record(
        ctx.session,
        actor="system",
        action="source_excluded",
        entity_type="discovery_run",
        entity_id=str(ctx.run_id),
        payload={"source_id": ctx.stat.source_id, "reason": reason},
        correlation_id=ctx.correlation_id,
    )


async def _run_source(ctx: RunContext, adapter: SourceAdapter) -> tuple[SourceRunStatus, int, int]:
    """Collect one source; returns (status, new_count, merged_count)."""
    stat = ctx.stat
    new_count = 0
    merged_count = 0
    source_status = SourceRunStatus.OK
    try:
        async for candidate in adapter.fetch_candidates(ctx):
            if stat.found > settings.discovery_max_items_per_source:
                break
            # Defensive re-cap: adapters sanitize, the runner enforces again (CMP-06).
            candidate.text = strip_html_to_text(candidate.text)
            candidate.normalized = _renormalize(candidate.normalized)
            master, status = await ingest_candidate(ctx.session, candidate, run_id=ctx.run_id)
            if status == "NEW":
                new_count += 1
            elif status == "MERGED":
                merged_count += 1
            # Fill-if-missing enrichment (FR-062) — same transaction, no extra fetch
            # when the homepage was already visited or the fields already exist.
            await enrich_homepage(
                master, client=ctx.client, website=candidate.normalized.get("website")
            )
    except ParseError as exc:
        stat.reject(exc.reason)
        if exc.reason == RejectReason.BLOCKED:
            source_status = SourceRunStatus.BLOCKED
            await _audit_exclusion(ctx, exc.reason.value)
        elif exc.reason == RejectReason.DISABLED:
            source_status = SourceRunStatus.DISABLED
        else:
            source_status = SourceRunStatus.ERROR
    except (RobotsDeniedError, httpx.HTTPStatusError) as exc:
        # Pitfall 4: never retry harder — block this source for the whole run.
        stat.reject(RejectReason.BLOCKED)
        source_status = SourceRunStatus.BLOCKED
        await _audit_exclusion(ctx, RejectReason.BLOCKED.value)
        logger.warning(
            "discovery source {} blocked: {} — source stopped for this run",
            stat.source_id,
            exc,
        )
    except Exception:  # noqa: BLE001 — one source must never fail the whole run
        source_status = SourceRunStatus.ERROR
        logger.exception("discovery source {} failed", stat.source_id)
    else:
        if stat.found == 0:
            source_status = SourceRunStatus.EMPTY
    return source_status, new_count, merged_count


async def execute_run(run_id: UUID, *, client_factory: ClientFactory | None = None) -> None:
    """Execute one discovery run: collect → normalize → dedup → enrich → persist.

    All rows (candidates, lineage, per-source stats, run totals, audits) commit
    in ONE transaction — the stats invariants are observable without sleeps.
    """
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        run = await session.get(DiscoveryRun, run_id)
        if run is None:
            raise RuntimeError(f"discovery run {run_id} not found")
        build_client = (
            client_factory if client_factory is not None else _default_client_factory(session)
        )
        await AuditService.record(
            session,
            actor="system",
            action="discovery_run_started",
            entity_type="discovery_run",
            entity_id=str(run.id),
            payload={"trigger_source": run.trigger_source},
            correlation_id=run.correlation_id,
        )
        total_candidates = 0
        failed_sources = 0
        for source_id, adapter_cls, enabled, _display, _short in registry.all_sources():
            if not enabled:
                session.add(
                    DiscoveryRunSourceStat(
                        run_id=run.id,
                        source_id=source_id,
                        status=SourceRunStatus.DISABLED,
                    )
                )
                continue
            adapter = adapter_cls()
            stat = SourceStatCollector(source_id)
            ctx = RunContext(
                run_id=run.id,
                correlation_id=run.correlation_id,
                client=build_client(adapter),
                session=session,
                stat=stat,
            )
            source_status, new_count, merged_count = await _run_source(ctx, adapter)
            total_candidates += new_count + merged_count
            if source_status in (SourceRunStatus.BLOCKED, SourceRunStatus.ERROR):
                failed_sources += 1
            session.add(
                DiscoveryRunSourceStat(
                    run_id=run.id,
                    source_id=source_id,
                    status=source_status,
                    requests_made=stat.requests_made,
                    found=stat.found,
                    parsed_ok=stat.parsed_ok,
                    rejected=stat.rejected,
                    new_count=new_count,
                    merged_count=merged_count,
                    rejection_buckets=stat.rejection_buckets,
                )
            )
        run.status = RunStatus.PARTIAL if failed_sources else RunStatus.COMPLETED
        run.total_candidates = total_candidates
        run.finished_at = datetime.now(UTC)
        await AuditService.record(
            session,
            actor="system",
            action="run_finished",
            entity_type="discovery_run",
            entity_id=str(run.id),
            payload={
                "status": run.status.value,
                "total_candidates": total_candidates,
                "failed_sources": failed_sources,
            },
            correlation_id=run.correlation_id,
        )
        await session.commit()
