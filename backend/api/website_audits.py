"""Website audits pages + owner-guarded trigger (AUDT-01..04).

T-03-01: pages render only code-built structured view dicts — never ORM rows,
never raw stored payloads. The trigger is enqueue-only (D-40): a RUNNING
WebsiteAudit row + OutboxEvent(topic="audit.run"), consumed by the audits
worker — this endpoint never executes the audit (RESEARCH Pattern 2). Re-audit
inserts a NEW row — history is never overwritten (D-39).
"""

from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import config
from backend.auth.owner import get_current_owner
from backend.auth.session import clear_flash, read_flash, set_flash
from backend.database import (
    AuditStatus,
    Business,
    OutboxEvent,
    WebsiteAudit,
    get_db,
)
from backend.services.audit import AuditService
from backend.services.discovery.normalize import normalize_domain

router = APIRouter(prefix="/website-audits")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

_ACTIVE_PAGE = "website_audits"

_STATUS_LABELS = {
    AuditStatus.RUNNING: "In progress",
    AuditStatus.COMPLETED: "Complete",
    AuditStatus.FAILED: "Failed",
}

_STATUS_BADGES = {
    AuditStatus.RUNNING: "running",
    AuditStatus.COMPLETED: "complete",
    AuditStatus.FAILED: "failed",
}

# Link status → (label, badge) — UI-SPEC §Color table, stored runner statuses.
_LINK_STATUS_VIEW = {
    "ok": ("OK", "ok"),
    "redirect": ("Redirect", "partial"),
    "broken": ("Broken", "failed"),
    "robots_denied": ("Robots blocked", "disabled"),
    "timeout": ("Timeout", "error"),
    "skipped": ("Skipped", "excluded"),
}

# Conversion-gap kind → (label, description) — fixed table (UI-SPEC D-36 rules).
_GAP_VIEWS = {
    "missing_contact_form": (
        "No contact form found",
        "No form with an action, mailto, or tel target was found on the page.",
    ),
    "form_no_action": (
        "Form without a submission target",
        "A form exists but has no action, mailto, or tel target set.",
    ),
    "missing_cta": (
        "No call-to-action found",
        "No prominent call-to-action link or button was found on the page.",
    ),
    "no_direct_contact": (
        "No email or phone link found",
        "No mailto or tel link was found on the page.",
    ),
    "no_phone_listed": (
        "No phone number listed",
        "No phone number is listed on the page.",
    ),
}

_CWV_METRICS = ("LCP", "INP", "CLS", "TTFB")

_INP_ESTIMATION_NOTES = {
    "scripted_event_timing": "INP estimated from scripted interaction event timing",
    "longtask_proxy": "INP estimated from long-task proxy",
}


def _confidence_label(confidence: float | None) -> str:
    """High / Medium / Low confidence — never a raw float on screen."""
    if confidence is None:
        return "Low confidence"
    if confidence >= 0.8:
        return "High confidence"
    if confidence >= 0.5:
        return "Medium confidence"
    return "Low confidence"


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


def _overall_score_display(audit: WebsiteAudit) -> str:
    """Rounded integer mean of the 4 dimension scores; '—' while RUNNING/FAILED.

    Display-only aggregation — never stored, never affects scoring (UI-SPEC).
    """
    if audit.status != AuditStatus.COMPLETED:
        return "—"
    scores = [
        audit.performance_score or 0,
        audit.accessibility_score or 0,
        audit.seo_score or 0,
        audit.mobile_score or 0,
    ]
    return str(round(mean(scores)))


def _status_label(status: AuditStatus) -> str:
    return _STATUS_LABELS.get(status, status.value)


def _status_badge(status: AuditStatus) -> str:
    return _STATUS_BADGES.get(status, status.value.lower())


def _cwv_row(
    metric: str, value_display: str, methodology_label: str, methodology_badge: str
) -> dict[str, str]:
    return {
        "metric": metric,
        "value_display": value_display,
        "methodology_label": methodology_label,
        "methodology_badge": methodology_badge,
    }


def _cwv_views(audit: WebsiteAudit) -> list[dict[str, str]]:
    """Fixed-order CWV rows (LCP · INP · CLS · TTFB) with honest methodology.

    Rendered metrics measured in a real browser are "Measured"; the lab INP is
    always an estimate ("Estimated"); anything absent is "Not assessed" — never
    a guessed value (D-34).
    """
    cwv = audit.cwv or {}
    ttfb_ms = cwv.get("ttfb_ms")
    lcp_ms = cwv.get("lcp_ms")
    cls = cwv.get("cls")
    inp_ms = cwv.get("inp_ms")

    def _metric_value(ms_or_value: Any, kind: str) -> str:
        if ms_or_value is None:
            return "—"
        if kind == "lcp":
            return f"{ms_or_value / 1000:.1f}s"
        if kind == "cls":
            return f"{ms_or_value:.2f}"
        return f"{ms_or_value}ms"

    rows = [
        _cwv_row(
            "LCP",
            _metric_value(lcp_ms, "lcp"),
            "Measured" if lcp_ms is not None else "Not assessed",
            "ok" if lcp_ms is not None else "expired",
        ),
        _cwv_row(
            "INP",
            _metric_value(inp_ms, "inp"),
            "Estimated" if inp_ms is not None else "Not assessed",
            "partial" if inp_ms is not None else "expired",
        ),
        _cwv_row(
            "CLS",
            _metric_value(cls, "cls"),
            "Measured" if cls is not None else "Not assessed",
            "ok" if cls is not None else "expired",
        ),
        _cwv_row(
            "TTFB",
            _metric_value(ttfb_ms, "ttfb"),
            "Measured" if ttfb_ms is not None else "Not assessed",
            "ok" if ttfb_ms is not None else "expired",
        ),
    ]
    return rows


def _cwv_notes(audit: WebsiteAudit) -> list[str]:
    """Stored methodology notes + the INP estimation label, pre-joined."""
    cwv = audit.cwv or {}
    methodology = cwv.get("methodology", {})
    notes = list(methodology.get("notes") or [])
    estimation = methodology.get("inp_estimation")
    if estimation in _INP_ESTIMATION_NOTES:
        notes.append(_INP_ESTIMATION_NOTES[estimation])
    return notes


def _detection_view(item: dict[str, Any]) -> dict[str, Any]:
    """Structured detection item: name + confidence label — never raw floats."""
    return {
        "name": item.get("name") or "—",
        "category": item.get("category") or "",
        "confidence_label": _confidence_label(item.get("confidence")),
    }


def _link_kind(url: str, site_domain: str | None) -> str:
    """Internal vs External by registered domain (runner's own bucketing rule)."""
    if site_domain and normalize_domain(url) == site_domain:
        return "Internal"
    return "External"


def _broken_link_views(
    links: list[dict[str, Any]] | None, site_domain: str | None
) -> list[dict[str, str]]:
    """Structured broken-link rows — every value pre-formatted (T-03-01)."""
    views: list[dict[str, str]] = []
    for link in links or []:
        status = link.get("status") or ""
        label, badge = _LINK_STATUS_VIEW.get(status, (status or "—", "excluded"))
        if status in ("redirect", "broken"):
            label = f"{label} {link.get('status_code')}"
        views.append(
            {
                "url": link.get("url") or "—",
                "kind_label": _link_kind(link.get("url") or "", site_domain),
                "status_label": label,
                "status_badge": badge,
            }
        )
    return views


def _gap_views(gaps: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """Fixed label + description pairs from the D-36 rules table."""
    views: list[dict[str, str]] = []
    for gap in gaps or []:
        kind = gap.get("kind") or ""
        label, description = _GAP_VIEWS.get(kind, (kind or "—", ""))
        views.append({"label": label, "description": description})
    return views


def _to_audit_view(audit: WebsiteAudit, site_domain: str | None) -> dict[str, Any]:
    """Structured-only audit view (T-03-01) — never the ORM row itself."""
    cms = audit.cms
    hosting = audit.hosting
    return {
        "audit_id": audit.id,
        "status": audit.status.value,
        "status_label": _status_label(audit.status),
        "status_badge": _status_badge(audit.status),
        "started_at_display": _format_started(audit.started_at),
        "audit_version": audit.audit_version,
        "mode_label": (
            "Rendered (Playwright)"
            if (audit.cwv or {}).get("methodology", {}).get("measured_with") == "playwright"
            else "Static only"
        ),
        "last_error": audit.last_error,
        "scores": {
            "performance": audit.performance_score,
            "accessibility": audit.accessibility_score,
            "seo": audit.seo_score,
            "mobile": audit.mobile_score,
        },
        "overall_score_display": _overall_score_display(audit),
        "cwv": _cwv_views(audit),
        "cwv_notes": _cwv_notes(audit),
        "tech_stack": [_detection_view(item) for item in (audit.tech_stack or [])],
        "cms": _detection_view(cms) if cms else None,
        "hosting": _detection_view(hosting) if hosting else None,
        "analytics": [_detection_view(item) for item in (audit.analytics or [])],
        "broken_links": _broken_link_views(audit.broken_links, site_domain),
        "gaps": _gap_views(audit.gaps),
    }


def _to_history_row(audit: WebsiteAudit) -> dict[str, Any]:
    """Structured history-row view (shared by lead + detail pages)."""
    return {
        "audit_id": audit.id,
        "started_at_display": _format_started(audit.started_at),
        "audit_version": audit.audit_version,
        "status": audit.status.value,
        "status_label": _status_label(audit.status),
        "status_badge": _status_badge(audit.status),
        "overall_score_display": _overall_score_display(audit),
    }


async def _load_business(session: AsyncSession, business_id: UUID) -> Business:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return business


@router.get("")
async def website_audits_page(
    request: Request,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Index: leads with ≥1 audit, one row per lead showing the latest audit."""
    lead_count = int(
        (await session.execute(select(func.count()).select_from(Business))).scalar_one()
    )
    latest_at = (
        select(WebsiteAudit.business_id, func.max(WebsiteAudit.started_at).label("latest"))
        .group_by(WebsiteAudit.business_id)
        .subquery()
    )
    rows = [
        {
            "business_id": business.id,
            "name": business.name,
            "website_url": business.website_url or "—",
            "audit_id": audit.id,
            "last_audited_display": _format_started(audit.started_at),
            "overall_score_display": _overall_score_display(audit),
            "status": audit.status.value,
            "status_label": _status_label(audit.status),
            "status_badge": _status_badge(audit.status),
        }
        for business, audit in (
            await session.execute(
                select(Business, WebsiteAudit)
                .join(latest_at, latest_at.c.business_id == Business.id)
                .join(
                    WebsiteAudit,
                    (WebsiteAudit.business_id == latest_at.c.business_id)
                    & (WebsiteAudit.started_at == latest_at.c.latest),
                )
                .order_by(latest_at.c.latest.desc())
                .limit(20)
            )
        ).all()
    ]
    flash = read_flash(request)
    response = templates.TemplateResponse(
        request,
        "website_audits_list.html",
        {
            "lead_count": lead_count,
            "rows": rows,
            "flash": flash,
            "agency_name": config.settings.agency_name,
            "owner_email": config.settings.owner_email,
            "active_page": _ACTIVE_PAGE,
        },
    )
    clear_flash(response)
    return response


@router.get("/lead/{business_id}")
async def website_audits_lead_page(
    request: Request,
    business_id: UUID,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Per-lead audit history, newest first (cap 10), with the trigger button."""
    business = await _load_business(session, business_id)
    audit_rows = (
        (
            await session.execute(
                select(WebsiteAudit)
                .where(WebsiteAudit.business_id == business.id)
                .order_by(WebsiteAudit.started_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    trigger_label = "Run audit" if not audit_rows else "Re-audit"
    flash = read_flash(request)
    response = templates.TemplateResponse(
        request,
        "website_audits_lead.html",
        {
            "lead": {
                "business_id": business.id,
                "name": business.name,
                "website_url": business.website_url or "—",
            },
            "audits": [_to_history_row(audit) for audit in audit_rows],
            "trigger_label": trigger_label,
            "flash": flash,
            "agency_name": config.settings.agency_name,
            "owner_email": config.settings.owner_email,
            "active_page": _ACTIVE_PAGE,
        },
    )
    clear_flash(response)
    return response


@router.post("/lead/{business_id}/run")
async def run_website_audit(
    request: Request,
    business_id: UUID,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Owner-guarded enqueue-only trigger (D-40): RUNNING row + event + audit log.

    The audits worker consumes OutboxEvent(topic="audit.run"); re-audit inserts
    a new row, never overwrites history (D-39).
    """
    _check_origin(request)
    business = await _load_business(session, business_id)
    audit = WebsiteAudit(
        business_id=business.id,
        status=AuditStatus.RUNNING,
        audit_version=config.settings.audit_version,
    )
    session.add(audit)
    await session.flush()
    session.add(
        OutboxEvent(
            topic="audit.run",
            payload={"audit_id": str(audit.id)},
        )
    )
    await AuditService.record(
        session,
        actor="owner",
        action="audit_triggered",
        entity_type="website_audit",
        entity_id=str(audit.id),
        payload={"business_id": str(business.id), "audit_version": audit.audit_version},
    )
    await session.commit()
    response = RedirectResponse(url=f"/website-audits/lead/{business.id}", status_code=302)
    set_flash(response, "Audit queued.", kind="success")
    return response


@router.get("/{audit_id}")
async def website_audit_detail_page(
    request: Request,
    audit_id: UUID,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Full audit detail; RUNNING/FAILED show a note and omit result sections."""
    audit = await session.get(WebsiteAudit, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    business = await session.get(Business, audit.business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    older_rows: list[dict[str, Any]] = []
    if audit.status == AuditStatus.COMPLETED:
        older_rows = [
            _to_history_row(row)
            for row in (
                (
                    await session.execute(
                        select(WebsiteAudit)
                        .where(
                            WebsiteAudit.business_id == audit.business_id,
                            WebsiteAudit.id != audit.id,
                        )
                        .order_by(WebsiteAudit.started_at.desc())
                        .limit(10)
                    )
                )
                .scalars()
                .all()
            )
        ]

    flash = read_flash(request)
    response = templates.TemplateResponse(
        request,
        "website_audit_detail.html",
        {
            "lead": {
                "business_id": business.id,
                "name": business.name,
                "website_url": business.website_url or "—",
            },
            "audit": _to_audit_view(audit, normalize_domain(business.website_url)),
            "older_audits": older_rows,
            "flash": flash,
            "agency_name": config.settings.agency_name,
            "owner_email": config.settings.owner_email,
            "active_page": _ACTIVE_PAGE,
        },
    )
    clear_flash(response)
    return response
