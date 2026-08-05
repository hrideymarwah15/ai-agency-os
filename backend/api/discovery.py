"""Discovery pipeline-state page + owner-guarded manual trigger (DASH-02, LEAD-05).

T-03-03: the mutating POST checks the Origin header (SameSite=Lax cookie is
primary; this is defense-in-depth) and every owner action is audited. T-03-01:
the page renders only code-built structured view dicts — never ORM rows, never
raw source payloads or sanitized prose (CMP-06). The trigger is enqueue-only
(D-12): a DiscoveryRun row + OutboxEvent, consumed by the outbox worker.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import config
from backend.auth.owner import get_current_owner
from backend.auth.session import clear_flash, read_flash, set_flash
from backend.database import (
    Business,
    BusinessSourceRecord,
    DiscoveryRun,
    DiscoveryRunSourceStat,
    OutboxEvent,
    RunStatus,
    SourceRunStatus,
    get_db,
)
from backend.services.audit import AuditService
from backend.services.discovery import registry

router = APIRouter(prefix="/discovery")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _source_columns() -> list[dict[str, str]]:
    """Registry-order source columns (T05) — drives the runs table + expanders.

    UI-SPEC §Page Anatomy column order: hn, reddit, yelp, google_places,
    mock_directory — the registry owns that order, not this module.
    """
    return [
        {"source_id": source_id, "short_name": short_name, "display_name": display_name}
        for source_id, _cls, _enabled, display_name, short_name in registry.all_sources()
    ]


_RUN_STATUS_LABELS = {
    RunStatus.RUNNING: "In progress",
    RunStatus.COMPLETED: "Complete",
    RunStatus.PARTIAL: "Partial",
    RunStatus.FAILED: "Failed",
}

_SOURCE_STATUS_LABELS = {
    SourceRunStatus.OK: "OK",
    SourceRunStatus.EMPTY: "Empty",
    SourceRunStatus.BLOCKED: "Blocked",
    SourceRunStatus.ERROR: "Error",
    SourceRunStatus.EXCLUDED: "Excluded",
    SourceRunStatus.DISABLED: "Disabled",
}

_TRIGGER_LABELS = {"MANUAL": "Manual", "SCHEDULER": "Scheduled"}


def _check_origin(request: Request) -> None:
    """T-03-03: reject cross-origin mutating POSTs with 403 (defense-in-depth)."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    expected = f"{request.url.scheme}://{request.url.netloc}"
    if origin != expected:
        raise HTTPException(status_code=403, detail="Cross-origin request rejected")


def _format_started(started_at: datetime) -> str:
    """Started renders as YYYY-MM-DD HH:MM UTC — never a raw datetime repr."""
    return started_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _format_duration(started_at: datetime, finished_at: datetime | None) -> str:
    """Duration renders as 45s / 2m 14s / 1h 03m; "In progress" while RUNNING."""
    if finished_at is None:
        return "In progress"
    total = max(0, int((finished_at - started_at).total_seconds()))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def _dedup_rate_display(new_count: int, merged_count: int) -> str:
    """Dedup rate as a percent string; "—" when there are no candidates."""
    if new_count + merged_count == 0:
        return "—"
    percent = round(merged_count / (new_count + merged_count) * 100)
    return f"Dedup rate {percent}%"


def _source_view(column: dict[str, str], stat: DiscoveryRunSourceStat | None) -> dict[str, Any]:
    """Structured per-source view: registry-order stats, or "—" placeholders."""
    if stat is None:
        return {
            "source_id": column["source_id"],
            "display_name": column["display_name"],
            "status": None,
            "status_label": "—",
            "requests_made": 0,
            "found": 0,
            "parsed_ok": 0,
            "rejected": 0,
            "new_count": 0,
            "merged_count": 0,
            "cell_display": "—",
            "rejection_line": "—",
        }
    buckets = stat.rejection_buckets or {}
    # JSONB round-trips lose dict insertion order (Postgres sorts keys) — render
    # in a stable, deterministic order: count desc, reason asc (plan example:
    # "missing_website 4 · too_short 2").
    ordered_buckets = sorted(buckets.items(), key=lambda item: (-item[1], item[0]))
    if stat.status in (SourceRunStatus.DISABLED, SourceRunStatus.EXCLUDED):
        cell_display = "—"
    else:
        cell_display = f"{stat.parsed_ok}/{stat.found}"
    return {
        "source_id": column["source_id"],
        "display_name": column["display_name"],
        "status": stat.status.value,
        "status_label": _SOURCE_STATUS_LABELS.get(stat.status, stat.status.value),
        "requests_made": stat.requests_made,
        "found": stat.found,
        "parsed_ok": stat.parsed_ok,
        "rejected": stat.rejected,
        "new_count": stat.new_count,
        "merged_count": stat.merged_count,
        "cell_display": cell_display,
        "rejection_line": " · ".join(f"{reason} {count}" for reason, count in ordered_buckets)
        or "—",
    }


def _to_run_view(
    run: DiscoveryRun,
    stats: dict[str, DiscoveryRunSourceStat],
    columns: list[dict[str, str]],
) -> dict[str, Any]:
    """Structured-only run view (T-03-01) — never the ORM row itself."""
    source_views: list[dict[str, Any]] = []
    totals: dict[str, int] = {"found": 0, "new": 0, "merged": 0}
    for column in columns:
        view = _source_view(column, stats.get(column["source_id"]))
        source_views.append(view)
        totals["found"] += view["found"]
        totals["new"] += view["new_count"]
        totals["merged"] += view["merged_count"]
    return {
        "id": run.id,
        "started_at": _format_started(run.started_at),
        "duration_display": _format_duration(run.started_at, run.finished_at),
        "status": run.status.value,
        "status_label": _RUN_STATUS_LABELS.get(run.status, run.status.value),
        "trigger_label": _TRIGGER_LABELS.get(run.trigger_source, run.trigger_source),
        "sources": source_views,
        "totals": totals,
        "dedup_rate_display": _dedup_rate_display(totals["new"], totals["merged"]),
    }


_ENRICHMENT_FIELD_COUNT = 10
_ENRICHMENT_FIELDS = (
    "name",
    "industry",
    "website_url",
    "email",
    "phone",
    "location",
    "employee_count",
    "rating",
    "review_count",
    "tech_stack",
)


def _enrichment_display(business: Business) -> str:
    """n/10 filled of the LEAD-02 field set (UI-SPEC §Leads table)."""
    filled = sum(
        1 for field in _ENRICHMENT_FIELDS if getattr(business, field) not in (None, [], "")
    )
    return f"{filled}/{_ENRICHMENT_FIELD_COUNT}"


def _to_lead_view(
    business: Business, found_at: datetime, lineage: list[dict[str, str]]
) -> dict[str, Any]:
    """Structured-only lead view (T-03-01) — every value pre-formatted."""
    employees = business.employee_count
    rating = business.rating
    return {
        "id": business.id,
        "name": business.name,
        "industry": business.industry or "—",
        "location": business.location or "—",
        "website_url": business.website_url or "—",
        "email": business.email or "—",
        "phone": business.phone or "—",
        "employee_count_display": str(employees) if employees is not None else "—",
        "rating_display": f"{rating:.1f}" if rating is not None else "—",
        "review_count": business.review_count or "—",
        "tech_stack": list(business.tech_stack or []),
        "tech_stack_display": ", ".join(business.tech_stack or []),
        "enrichment_display": _enrichment_display(business),
        "found_date": _format_started(found_at),
        "lineage": lineage,
    }


async def _lead_views(session: AsyncSession, columns: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Qualified leads (limit 20), newest first by first-discovered run.

    Lineage badges list DISTINCT sources in registry order (UI-SPEC §Leads
    table) — a business found by two sources renders two badges.
    """
    rows = (
        await session.execute(
            select(Business, func.min(DiscoveryRun.started_at).label("found_at"))
            .join(BusinessSourceRecord, BusinessSourceRecord.business_id == Business.id)
            .join(DiscoveryRun, DiscoveryRun.id == BusinessSourceRecord.run_id)
            .group_by(Business.id)
            .order_by(func.min(DiscoveryRun.started_at).desc())
            .limit(20)
        )
    ).all()
    ids = [business.id for business, _found_at in rows]
    lineage_sets: dict[UUID, set[str]] = {}
    if ids:
        records = (
            (
                await session.execute(
                    select(BusinessSourceRecord).where(BusinessSourceRecord.business_id.in_(ids))
                )
            )
            .scalars()
            .all()
        )
        for record in records:
            lineage_sets.setdefault(record.business_id, set()).add(record.source_id)
    short_names = {column["source_id"]: column["short_name"] for column in columns}
    return [
        _to_lead_view(
            business,
            found_at,
            [
                {"source_id": source_id, "short_name": short_names[source_id]}
                for source_id in short_names
                if source_id in lineage_sets.get(business.id, set())
            ],
        )
        for business, found_at in rows
    ]


def _enabled_source_count() -> int:
    """Count of enabled source flags (zero ⇒ the page renders the banner)."""
    s = config.settings
    return sum(
        (
            s.source_hn_enabled,
            s.source_reddit_enabled,
            s.source_yelp_enabled,
            s.source_google_places_enabled,
            s.source_mock_directory_enabled,
        )
    )


@router.get("")
async def discovery_page(
    request: Request,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Render pipeline state: recent runs, per-source metrics, qualified leads."""
    run_rows = list(
        (
            await session.execute(
                select(DiscoveryRun).order_by(DiscoveryRun.started_at.desc()).limit(10)
            )
        )
        .scalars()
        .all()
    )
    stat_rows: list[DiscoveryRunSourceStat] = []
    if run_rows:
        stat_rows = list(
            (
                await session.execute(
                    select(DiscoveryRunSourceStat).where(
                        DiscoveryRunSourceStat.run_id.in_([row.id for row in run_rows])
                    )
                )
            )
            .scalars()
            .all()
        )
    stats_by_run: dict[UUID, dict[str, DiscoveryRunSourceStat]] = {}
    for stat in stat_rows:
        stats_by_run.setdefault(stat.run_id, {})[stat.source_id] = stat

    columns = _source_columns()
    run_views = [_to_run_view(row, stats_by_run.get(row.id, {}), columns) for row in run_rows]

    table_source_totals = [
        {
            "source_id": column["source_id"],
            "found": sum(s.found for s in stat_rows if s.source_id == column["source_id"]),
        }
        for column in columns
    ]
    table_totals = {
        "found": sum(s.found for s in stat_rows),
        "new": sum(s.new_count for s in stat_rows),
        "merged": sum(s.merged_count for s in stat_rows),
    }

    flash = read_flash(request)
    response = templates.TemplateResponse(
        request,
        "discovery.html",
        {
            "enabled_source_count": _enabled_source_count(),
            "runs": run_views,
            "source_columns": columns,
            "table_source_totals": table_source_totals,
            "table_totals": table_totals,
            "table_dedup_rate_display": _dedup_rate_display(
                table_totals["new"], table_totals["merged"]
            ),
            "leads": await _lead_views(session, columns),
            "flash": flash,
            "agency_name": config.settings.agency_name,
            "owner_email": config.settings.owner_email,
            "active_page": "discovery",
        },
    )
    clear_flash(response)
    return response


@router.post("/run")
async def run_discovery(
    request: Request,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Owner-guarded manual trigger: enqueue one discovery run (D-28, D-12).

    Creates the DiscoveryRun + OutboxEvent + audit row in ONE transaction —
    the worker consumes the event, never this endpoint (RESEARCH Pattern 2).
    """
    _check_origin(request)
    run = DiscoveryRun(
        trigger_source="MANUAL", status=RunStatus.RUNNING, correlation_id=str(uuid4())
    )
    session.add(run)
    await session.flush()
    session.add(
        OutboxEvent(
            topic="discovery.run",
            payload={"run_id": str(run.id), "correlation_id": run.correlation_id},
        )
    )
    await AuditService.record(
        session,
        actor="owner",
        action="discovery_triggered",
        entity_type="discovery_run",
        entity_id=str(run.id),
        payload={"trigger_source": "MANUAL"},
        correlation_id=run.correlation_id,
    )
    await session.commit()
    response = RedirectResponse(url="/discovery", status_code=302)
    set_flash(response, "Discovery run queued.", kind="success")
    return response
