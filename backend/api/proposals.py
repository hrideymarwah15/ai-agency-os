"""Owner proposal lifecycle API and signed external client view."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import config
from backend.auth.owner import get_current_owner
from backend.database import Business, BusinessStatus, OutboxEvent, Proposal, ProposalStatus, get_db
from backend.services.audit import AuditService
from backend.services.proposal.generator import ProposalGenerator
from backend.services.proposal.pdf import PDFRenderer
from backend.services.proposal.templates import ComponentBlock

router = APIRouter(tags=["proposals"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
renderer = PDFRenderer()


class GenerateRequest(BaseModel):
    """Request an asynchronous proposal build."""

    lead_id: UUID
    meeting_notes: str = Field(default="", max_length=10000)
    package_name: str | None = Field(default=None, max_length=100)
    service_type: str | None = None


class EditRequest(BaseModel):
    """Replace one rendered proposal section."""

    section: ComponentBlock
    content: str = Field(min_length=1, max_length=100000)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.settings.session_secret, salt="proposal-client-v1")


def _proposal_dict(proposal: Proposal) -> dict[str, Any]:
    return {
        "id": str(proposal.id), "lead_id": str(proposal.business_id), "package_name": proposal.package_name,
        "service_type": proposal.service_type.value, "status": proposal.status.value, "version": proposal.version,
        "executive_summary": proposal.executive_summary, "website_audit": proposal.website_audit,
        "opportunity_analysis": proposal.opportunity_analysis, "scope": proposal.scope_of_work,
        "timeline": proposal.timeline, "pricing": proposal.pricing, "faqs": proposal.faqs,
        "testimonials": proposal.testimonials, "terms": proposal.terms, "next_steps": proposal.next_steps,
        "section_html": proposal.section_html, "full_html": proposal.full_html,
        "version_history": proposal.version_history, "owner_approved_at": proposal.owner_approved_at.isoformat() if proposal.owner_approved_at else None,
        "sent_at": proposal.sent_at.isoformat() if proposal.sent_at else None,
    }


async def _get_proposal(session: AsyncSession, proposal_id: UUID) -> Proposal:
    proposal = await session.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.post("/api/v1/proposals/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_proposal(
    body: GenerateRequest,
    owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Queue proposal generation; the request ID is the durable outbox ID."""
    if await session.get(Business, body.lead_id) is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    request_id = uuid4()
    session.add(OutboxEvent(id=request_id, topic="proposal.generate", payload={**body.model_dump(mode="json"), "triggered_by": "manual", "requested_by": owner}))
    await session.commit()
    return {"request_id": str(request_id), "status": "queued"}


@router.get("/api/v1/proposals")
async def list_proposals(
    proposal_status: ProposalStatus | None = Query(default=None, alias="status"),
    lead_id: UUID | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List owner proposals with bounded filters."""
    query = select(Proposal).order_by(Proposal.created_at.desc()).limit(100)
    if proposal_status:
        query = query.where(Proposal.status == proposal_status)
    if lead_id:
        query = query.where(Proposal.business_id == lead_id)
    if created_from:
        query = query.where(Proposal.created_at >= datetime.combine(created_from, datetime.min.time(), UTC))
    if created_to:
        query = query.where(Proposal.created_at < datetime.combine(created_to + timedelta(days=1), datetime.min.time(), UTC))
    return [_proposal_dict(item) for item in (await session.execute(query)).scalars().all()]


@router.get("/api/v1/proposals/{proposal_id}")
async def get_proposal(proposal_id: UUID, _owner: str = Depends(get_current_owner), session: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return all structured proposal data to the owner."""
    return _proposal_dict(await _get_proposal(session, proposal_id))


@router.get("/api/v1/proposals/{proposal_id}/html", response_class=HTMLResponse)
async def proposal_html(proposal_id: UUID, _owner: str = Depends(get_current_owner), session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """Return owner-authenticated printable proposal HTML."""
    proposal = await _get_proposal(session, proposal_id)
    return HTMLResponse(renderer.render_html(proposal.full_html or ""), headers={"X-Robots-Tag": "noindex, nofollow"})


@router.get("/api/v1/proposals/{proposal_id}/pdf")
async def proposal_pdf(proposal_id: UUID, _owner: str = Depends(get_current_owner), session: AsyncSession = Depends(get_db)) -> Response:
    """Render a proposal PDF locally with an enforced renderer timeout."""
    proposal = await _get_proposal(session, proposal_id)
    try:
        content = await renderer.render_pdf(proposal.full_html or "", Path(__file__).resolve().parents[2])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="proposal-{proposal.id}.pdf"', "X-Robots-Tag": "noindex, nofollow"})


@router.get("/api/v1/proposals/{proposal_id}/docx")
async def proposal_docx(proposal_id: UUID, _owner: str = Depends(get_current_owner), session: AsyncSession = Depends(get_db)) -> Response:
    """Return optional owner-editable DOCX or a clear dependency error."""
    proposal = await _get_proposal(session, proposal_id)
    try:
        content = renderer.render_docx(proposal.full_html or "")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@router.put("/api/v1/proposals/{proposal_id}")
async def edit_proposal(proposal_id: UUID, body: EditRequest, owner: str = Depends(get_current_owner), session: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Apply an owner edit, creating an immutable prior-section snapshot."""
    proposal = await _get_proposal(session, proposal_id)
    if proposal.status not in {ProposalStatus.DRAFT, ProposalStatus.APPROVED}:
        raise HTTPException(status_code=409, detail="Sent proposals cannot be edited")
    proposal = await ProposalGenerator().regenerate_section(session, proposal, body.section, body.content)
    await session.commit()
    return _proposal_dict(proposal)


@router.post("/api/v1/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: UUID, owner: str = Depends(get_current_owner), session: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Record explicit owner approval and enqueue contract generation."""
    proposal = await _get_proposal(session, proposal_id)
    if proposal.status != ProposalStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft proposals can be approved")
    proposal.status = ProposalStatus.APPROVED
    proposal.owner_approved_at = datetime.now(UTC)
    proposal.owner_approved_by = owner
    session.add(OutboxEvent(topic="contract.generate", payload={"proposal_id": str(proposal.id), "approved_by": owner}))
    await AuditService.record(session, actor=owner, action="proposal.approve", entity_type="proposal", entity_id=str(proposal.id), correlation_id=str(proposal.id), payload={"version": proposal.version})
    await session.commit()
    return _proposal_dict(proposal)


@router.post("/api/v1/proposals/{proposal_id}/send")
async def send_proposal(proposal_id: UUID, owner: str = Depends(get_current_owner), session: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Create signed client access and durable delivery handoff; no send is claimed here."""
    proposal = await _get_proposal(session, proposal_id)
    if proposal.status != ProposalStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Owner approval is required before delivery")
    business = await session.get(Business, proposal.business_id)
    if business is None or not business.email:
        raise HTTPException(status_code=409, detail="Client email is required before delivery handoff")
    nonce = secrets.token_urlsafe(24)
    token = _serializer().dumps({"proposal_id": str(proposal.id), "nonce": nonce})
    proposal.client_access_token_hash = hashlib.sha256(token.encode()).hexdigest()
    proposal.client_access_token_expires_at = proposal.expires_at or datetime.now(UTC) + timedelta(days=14)
    proposal.status = ProposalStatus.SENT
    proposal.sent_at = datetime.now(UTC)
    business.status = BusinessStatus.NEGOTIATING
    client_path = f"/client/proposals/{proposal.id}?token={token}"
    session.add(OutboxEvent(topic="proposal.deliver", payload={"proposal_id": str(proposal.id), "recipient": business.email, "client_path": client_path, "formats": ["html", "pdf"]}))
    await AuditService.record(session, actor=owner, action="proposal.delivery_queued", entity_type="proposal", entity_id=str(proposal.id), correlation_id=str(proposal.id), payload={"version": proposal.version, "channel": "durable_outbox"})
    await session.commit()
    return {"id": str(proposal.id), "status": "delivery_queued", "client_path": client_path}


@router.get("/client/proposals/{proposal_id}", response_class=HTMLResponse)
async def client_proposal(proposal_id: UUID, token: str, session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """Validate signed, expiring client access and record the first view."""
    proposal = await _get_proposal(session, proposal_id)
    try:
        payload = _serializer().loads(token, max_age=60 * 60 * 24 * 14)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=403, detail="Invalid or expired proposal link") from exc
    valid_hash = proposal.client_access_token_hash and secrets.compare_digest(proposal.client_access_token_hash, hashlib.sha256(token.encode()).hexdigest())
    if payload.get("proposal_id") != str(proposal.id) or not valid_hash or not proposal.client_access_token_expires_at or proposal.client_access_token_expires_at < datetime.now(UTC):
        raise HTTPException(status_code=403, detail="Invalid or expired proposal link")
    proposal.viewed_at = proposal.viewed_at or datetime.now(UTC)
    await AuditService.record(session, actor="client", action="proposal.view", entity_type="proposal", entity_id=str(proposal.id), correlation_id=str(proposal.id), payload={})
    await session.commit()
    return HTMLResponse(renderer.render_html(proposal.full_html or ""), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})


@router.get("/proposals/{proposal_id}", response_class=HTMLResponse)
async def proposal_builder(request: Request, proposal_id: UUID, owner: str = Depends(get_current_owner), session: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """Render the owner proposal builder shell."""
    proposal = await _get_proposal(session, proposal_id)
    return templates.TemplateResponse(request, "proposal.html", {"proposal": proposal, "owner_email": owner, "agency_name": config.settings.agency_name, "active_page": "proposals"})
