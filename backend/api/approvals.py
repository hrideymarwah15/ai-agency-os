"""Owner approval queue — queue page + approve/reject/escalate + demo trigger.

T-03-03: every mutating POST checks the Origin header (SameSite=Lax cookie is
primary; this is defense-in-depth) and all owner actions are audited. T-03-01:
the queue renders only code-built structured fields — never raw LLM prose.
"""

from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from backend import config
from backend.auth.owner import get_current_owner
from backend.auth.session import clear_flash, read_flash, set_flash
from backend.database import ApprovalRequest, ApprovalStatus, get_db
from backend.services import approvals as approvals_service
from backend.workflows import get_ceo_review_graph
from backend.workflows.ceo_graph import demo_start_state

router = APIRouter(prefix="/approvals")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

_ACTIONS = ("approve", "reject", "escalate")

_STATUS_LABELS = {
    ApprovalStatus.PENDING: "Pending",
    ApprovalStatus.APPROVED: "Approved",
    ApprovalStatus.REJECTED: "Rejected",
    ApprovalStatus.ESCALATED: "Escalated",
    ApprovalStatus.EXPIRED: "Expired",
}

# T-03-01: the queue renders ONLY these structured detail keys (whitelist).
_DETAIL_LABELS = {
    "business_name": "Business",
    "package_name": "Package",
    "service_type": "Service",
    "scope_summary": "Scope",
    "min_price": "Minimum price",
    "service": "Service",
    "scope": "Scope",
}


def _check_origin(request: Request) -> None:
    """T-03-03: reject cross-origin mutating POSTs with 403 (defense-in-depth)."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    expected = f"{request.url.scheme}://{request.url.netloc}"
    if origin != expected:
        raise HTTPException(status_code=403, detail="Cross-origin request rejected")


def _format_amount(row: ApprovalRequest) -> str:
    """Amounts render as 2dp grouped currency strings — never float reprs."""
    raw = row.context.get("amount", "0")
    try:
        return f"{Decimal(str(raw)):,.2f}"
    except (InvalidOperation, ValueError):
        return str(raw)


def _to_view(row: ApprovalRequest) -> dict:
    """Structured-only view model for the queue template (T-03-01)."""
    details = [
        {"label": label, "value": row.context["details"][key]}
        for key, label in _DETAIL_LABELS.items()
        if key in (row.context.get("details") or {})
    ]
    return {
        "id": row.id,
        "status": row.status.value,
        "status_label": _STATUS_LABELS.get(row.status, row.status.value),
        "action_type": row.action_type,
        "entity": row.context.get("entity") or row.entity_id or "Unknown",
        "amount_display": _format_amount(row),
        "currency": row.context.get("currency", ""),
        "created_at": row.created_at,
        "details": details,
        "decision_reason": row.decision_reason,
    }


@router.get("")
async def approvals_page(
    request: Request,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Render the approval queue: PENDING first (oldest first), decided newest-first."""
    rows = await approvals_service.list_requests(session)
    pending_count = sum(1 for row in rows if row.status == ApprovalStatus.PENDING)
    flash = read_flash(request)
    response = templates.TemplateResponse(
        request,
        "approvals.html",
        {
            "requests": [_to_view(row) for row in rows],
            "pending_count": pending_count,
            "demo_enabled": config.settings.mock_mode,
            "flash": flash,
            "agency_name": config.settings.agency_name,
            "owner_email": config.settings.owner_email,
            "active_page": "approvals",
        },
    )
    clear_flash(response)
    return response


@router.post("/demo/start")
async def demo_start(
    request: Request,
    _owner: str = Depends(get_current_owner),
) -> Response:
    """Owner-guarded dev trigger: start a gated proposal review (mock_mode only)."""
    _check_origin(request)
    if not config.settings.mock_mode:
        raise HTTPException(status_code=404, detail="Demo trigger requires MOCK_MODE")
    graph = await get_ceo_review_graph()
    thread_id = str(uuid4())
    await graph.ainvoke(
        demo_start_state(str(uuid4())),
        config={"configurable": {"thread_id": thread_id}},
    )
    response = RedirectResponse(url="/approvals", status_code=302)
    set_flash(
        response,
        "Demo started — a gated proposal review is waiting for approval.",
        kind="success",
    )
    return response


@router.post("/{request_id}/{action}")
async def act_on_request(
    request: Request,
    request_id: UUID,
    action: str,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Approve / reject / escalate one queue row; flash + 302 back to the queue."""
    _check_origin(request)
    if action not in _ACTIONS:
        raise HTTPException(status_code=404, detail="Unknown approval action")
    row = await approvals_service.get_request(session, request_id)
    entity = row.context.get("entity") or row.entity_id or "Unknown"
    reason = ""

    if action == "reject":
        form = await request.form()
        reason = str(form.get("reason", "")).strip()
        if not reason:
            # 400 re-render: the row stays PENDING, nothing was decided.
            flash = {"message": "A reason is required to reject.", "kind": "error"}
            error_response = templates.TemplateResponse(
                request,
                "approvals.html",
                {
                    "requests": [_to_view(r) for r in await approvals_service.list_requests(session)],
                    "pending_count": await _pending_count(session),
                    "demo_enabled": config.settings.mock_mode,
                    "flash": flash,
                    "agency_name": config.settings.agency_name,
                    "owner_email": config.settings.owner_email,
                    "active_page": "approvals",
                },
                status_code=400,
            )
            clear_flash(error_response)
            return error_response

    graph = await get_ceo_review_graph()
    if action == "approve":
        await approvals_service.approve(session, graph, request_id)
        message, kind = f"Approved — {entity}. The agent workflow has resumed.", "success"
    elif action == "reject":
        await approvals_service.reject(session, graph, request_id, reason)
        message, kind = f"Rejected — {entity}. The workflow has been halted.", "success"
    else:
        await approvals_service.escalate(session, request_id, reason or "")
        message, kind = f"Escalated — {entity}. Flagged for review.", "success"

    response = RedirectResponse(url="/approvals", status_code=302)
    set_flash(response, message, kind=kind)
    return response


async def _pending_count(session: AsyncSession) -> int:
    """Pending rows count for the nav badge (shared with the queue page)."""
    rows = await approvals_service.list_requests(session, status=ApprovalStatus.PENDING)
    return len(rows)
