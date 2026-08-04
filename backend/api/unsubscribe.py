"""Public one-click unsubscribe — token-gated GET, no session (CMP-04, T-05-02).

The signed token IS the identity: no email parameter is accepted, so a valid
link can only unsubcribe the address the agency itself signed (itsdangerous
canonical use case). Tampered or expired tokens render the invalid state and
never touch the suppression list.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from backend import config
from backend.database import get_db
from backend.services.audit import AuditService
from backend.services.compliance import suppression

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

# CMP-04: 7-day signed unsubscribe token, tamper-proof.
serializer = URLSafeTimedSerializer(config.settings.session_secret, salt="unsubscribe")

_UNSUBSCRIBE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


@router.get("/unsubscribe")
async def unsubscribe(
    request: Request,
    t: str,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Unsubscribe the signed email, or render the invalid-link state."""
    try:
        email = serializer.loads(t, max_age=_UNSUBSCRIBE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return _render(request, state="invalid")

    await suppression.add(session, email=email, reason="one-click-unsubscribe")
    await AuditService.record(
        session,
        actor="system",
        action="unsubscribed",
        entity_type="email",
        entity_id=email,
        payload={"reason": "one-click-unsubscribe"},
    )
    await session.commit()
    return _render(request, state="success")


def _render(request: Request, *, state: str) -> Response:
    """Render the unsubscribe page for the given state with the UI-SPEC copy."""
    return templates.TemplateResponse(
        request,
        "unsubscribe.html",
        {
            "state": state,
            "agency_name": config.settings.agency_name,
            # Rendered only as page copy — NOT passed as owner_email, so the
            # public page never shows the owner nav bar or logout form.
            "contact_email": config.settings.owner_email,
        },
    )
