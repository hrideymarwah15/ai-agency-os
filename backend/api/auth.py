"""Owner login/logout routes — uniform failure copy, Argon2id verify (T-01-01)."""

from pathlib import Path
from uuid import uuid4

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from backend import config
from backend.auth.owner import get_current_owner
from backend.auth.session import (
    clear_flash,
    clear_session_cookie,
    create_session_cookie,
    read_flash,
)
from backend.database import get_db
from backend.services.audit import AuditService

router = APIRouter(prefix="/auth")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

# One shared verifier instance — Argon2id parameter computation is expensive.
_PASSWORD_HASH = PasswordHash.recommended()

_INVALID_CREDENTIALS = "Invalid email or password."


@router.get("/login")
async def login_page(request: Request) -> Response:
    """Render the login page (or bounce already-authenticated owners to /audit)."""
    try:
        get_current_owner(request)
    except HTTPException:
        pass
    else:
        return RedirectResponse(url="/audit", status_code=302)
    flash = read_flash(request)
    response = templates.TemplateResponse(
        request,
        "login.html",
        {"flash": flash, "agency_name": config.settings.agency_name},
    )
    clear_flash(response)
    return response


@router.post("/login")
async def login(request: Request, session: AsyncSession = Depends(get_db)) -> Response:
    """Verify credentials; success sets the session cookie and audit-logs owner_login."""
    form = await request.form()
    email = str(form.get("email", ""))
    password = str(form.get("password", ""))

    if email == config.settings.owner_email and password:
        # Timing uniform per T-01-01: argon2 verify only runs against the owner hash.
        valid = await anyio.to_thread.run_sync(
            _PASSWORD_HASH.verify, password, config.settings.owner_password_hash
        )
    else:
        valid = False

    if not valid:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "flash": {"message": _INVALID_CREDENTIALS, "kind": "error"},
                "agency_name": config.settings.agency_name,
            },
            status_code=200,
        )

    await AuditService.record(
        session,
        actor="owner",
        action="owner_login",
        entity_type="owner",
        entity_id=config.settings.owner_email,
        payload={"email": config.settings.owner_email},
        correlation_id=str(uuid4()),
    )
    await session.commit()

    response = RedirectResponse(url="/audit", status_code=302)
    create_session_cookie(response, config.settings.owner_email)
    return response


@router.post("/logout")
async def logout(
    request: Request,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Clear the session cookie and audit-log owner_logout (POST-only, T-01-03)."""
    await AuditService.record(
        session,
        actor="owner",
        action="owner_logout",
        entity_type="owner",
        entity_id=config.settings.owner_email,
        payload={},
        correlation_id=str(uuid4()),
    )
    await session.commit()

    response = RedirectResponse(url="/auth/login", status_code=302)
    clear_session_cookie(response)
    return response
