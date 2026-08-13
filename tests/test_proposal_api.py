"""Proposal owner API registration and lifecycle unit tests."""

from decimal import Decimal
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.proposals import (
    EditRequest,
    _serializer,
    _validate_owner_html,
    approve_proposal,
    client_proposal,
    edit_proposal,
    proposal_docx,
    proposal_pdf,
    send_proposal,
)
from backend.database import Business, BusinessStatus, Proposal, ProposalStatus, ServiceType
from backend.main import app


class FakeSession:
    def __init__(self, proposal: Proposal, business: Business) -> None:
        self.proposal = proposal
        self.business = business
        self.added = []

    async def get(self, model, identifier):
        if model is Proposal:
            return self.proposal
        if model is Business:
            return self.business
        return None

    def add(self, value) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        return None


def _objects(status: ProposalStatus = ProposalStatus.DRAFT, email: str | None = "client@example.com"):
    business = Business(id=uuid4(), name="Acme", email=email, status=BusinessStatus.CONTACTED)
    proposal = Proposal(id=uuid4(), business_id=business.id, package_name="Starter", service_type=ServiceType.WEBSITE, proposed_price=Decimal("50000"), min_price=Decimal("40000"), current_offered_price=Decimal("50000"), scope_summary="Scope", status=status, pricing={"recommended_price": 50000}, section_html={}, version_history=[])
    return proposal, business


def test_routes_registered() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    paths = schema["paths"]
    assert "/api/v1/proposals/generate" in paths
    assert "/api/v1/proposals/{proposal_id}/pdf" in paths
    assert "/api/v1/proposals/{proposal_id}/approve" in paths
    assert "/client/proposals/{proposal_id}" in paths


def test_owner_edit_rejects_executable_html() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_owner_html('<script>alert("x")</script>')
    assert exc.value.status_code == 422


@pytest.mark.parametrize(
    "content",
    [
        '<img src=x OnErRoR = "alert(1)">',
        '<a href="java&#x73;cript:alert(1)">x</a>',
        '<a href=" data:text/html;base64,abc">x</a>',
        '<IFRAME src="https://example.com"></IFRAME>',
        '<style>body{display:none}</style>',
        '<form action="https://example.com"><input></form>',
        '<p class="unsafe">x</p>',
    ],
)
def test_owner_edit_rejects_sanitizer_bypasses(content: str) -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_owner_html(content)
    assert exc.value.status_code == 422


def test_owner_edit_preserves_safe_formatting() -> None:
    content = _validate_owner_html('<h2>Scope</h2><p><strong>Safe</strong> <a href="https://example.com">link</a></p>')
    assert content == '<h2>Scope</h2><p><strong>Safe</strong> <a href="https://example.com">link</a></p>'


def test_approve_then_send_creates_contract_and_delivery_outbox() -> None:
    proposal, business = _objects()
    session = FakeSession(proposal, business)
    approved = asyncio.run(approve_proposal(proposal.id, "owner@test", session))
    assert approved["status"] == "APPROVED"
    assert any(item.topic == "contract.generate" for item in session.added if hasattr(item, "topic"))
    sent = asyncio.run(send_proposal(proposal.id, "owner@test", session))
    assert sent["status"] == "DELIVERY_QUEUED"
    assert proposal.status == ProposalStatus.DELIVERY_QUEUED
    assert business.status == BusinessStatus.CONTACTED
    assert any(item.topic == "proposal.deliver" for item in session.added if hasattr(item, "topic"))


def test_send_requires_approval_and_client_email() -> None:
    proposal, business = _objects()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(send_proposal(proposal.id, "owner@test", FakeSession(proposal, business)))
    assert exc.value.status_code == 409
    proposal.status = ProposalStatus.APPROVED
    business.email = None
    with pytest.raises(HTTPException) as exc:
        asyncio.run(send_proposal(proposal.id, "owner@test", FakeSession(proposal, business)))
    assert exc.value.status_code == 409


def test_pricing_discount_is_bounded_by_negotiation_limits() -> None:
    proposal, business = _objects()
    proposal.pricing = {"recommended_price": 50000, "max_discount_pct": 15, "negotiation_limits": {"max_discount_pct": 15}}
    session = FakeSession(proposal, business)
    updated = asyncio.run(edit_proposal(proposal.id, EditRequest(section="pricing", discount_pct=10), "owner@test", session))
    assert updated["pricing"]["final_price"] == 45000
    assert float(proposal.final_price) == 45000
    with pytest.raises(HTTPException) as exc:
        asyncio.run(edit_proposal(proposal.id, EditRequest(section="pricing", discount_pct=16), "owner@test", session))
    assert exc.value.status_code == 422


def test_signed_client_route_records_view_and_rejects_queued() -> None:
    proposal, business = _objects(ProposalStatus.SENT)
    session = FakeSession(proposal, business)
    token = _serializer().dumps({"proposal_id": str(proposal.id), "nonce": "n"})
    import hashlib
    from datetime import UTC, datetime, timedelta

    proposal.client_access_token_hash = hashlib.sha256(token.encode()).hexdigest()
    proposal.client_access_token_expires_at = datetime.now(UTC) + timedelta(days=1)
    proposal.full_html = "<html><head></head><body>Proposal</body></html>"
    response = asyncio.run(client_proposal(proposal.id, token, session))
    assert response.status_code == 200
    assert proposal.viewed_at is not None
    assert any(getattr(item, "correlation_id", None) == str(proposal.id) for item in session.added)
    proposal.status = ProposalStatus.DELIVERY_QUEUED
    with pytest.raises(HTTPException) as exc:
        asyncio.run(client_proposal(proposal.id, token, session))
    assert exc.value.status_code == 403


def test_optional_pdf_and_docx_fail_as_503(monkeypatch) -> None:
    proposal, business = _objects()
    session = FakeSession(proposal, business)

    async def unavailable_pdf(*args, **kwargs):
        raise RuntimeError("PDF unavailable")

    def unavailable_docx(*args, **kwargs):
        raise RuntimeError("DOCX unavailable")

    from backend.api import proposals as proposal_api

    monkeypatch.setattr(proposal_api.renderer, "render_pdf", unavailable_pdf)
    monkeypatch.setattr(proposal_api.renderer, "render_docx", unavailable_docx)
    with pytest.raises(HTTPException) as pdf_error:
        asyncio.run(proposal_pdf(proposal.id, "owner@test", session))
    assert pdf_error.value.status_code == 503
    with pytest.raises(HTTPException) as docx_error:
        asyncio.run(proposal_docx(proposal.id, "owner@test", session))
    assert docx_error.value.status_code == 503
