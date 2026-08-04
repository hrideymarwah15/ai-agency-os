"""Read-only audit log route — owner-guarded DB read proving the skeleton."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from backend import config
from backend.auth.owner import get_current_owner
from backend.auth.session import clear_flash, read_flash
from backend.database import get_db
from backend.services.audit import AuditService

router = APIRouter(prefix="/audit")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("")
async def audit_page(
    request: Request,
    correlation_id: str | None = None,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Render the audit log, newest first — optionally filtered to one correlation trail.

    Read-only (T-02-02): owner-guarded; the correlation_id is used as a query
    filter only and is never echoed into the rendered page (UI-SPEC security).
    """
    if correlation_id:
        entries = await AuditService.query(session, correlation_id=correlation_id)
    else:
        entries = await AuditService.list_recent(session, limit=100)
    flash = read_flash(request)
    response = templates.TemplateResponse(
        request,
        "audit.html",
        {
            "entries": entries,
            "flash": flash,
            "agency_name": config.settings.agency_name,
            "owner_email": config.settings.owner_email,
            "active_page": "audit",
            "filter_active": correlation_id is not None,
        },
    )
    clear_flash(response)
    return response
