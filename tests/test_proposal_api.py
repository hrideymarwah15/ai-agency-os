"""Proposal owner API registration and lifecycle unit tests."""

from decimal import Decimal
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.proposals import _validate_owner_html, approve_proposal, send_proposal
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


def test_approve_then_send_creates_contract_and_delivery_outbox() -> None:
    proposal, business = _objects()
    session = FakeSession(proposal, business)
    approved = asyncio.run(approve_proposal(proposal.id, "owner@test", session))
    assert approved["status"] == "APPROVED"
    assert any(item.topic == "contract.generate" for item in session.added if hasattr(item, "topic"))
    sent = asyncio.run(send_proposal(proposal.id, "owner@test", session))
    assert sent["status"] == "delivery_queued"
    assert proposal.status == ProposalStatus.SENT
    assert business.status == BusinessStatus.NEGOTIATING
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
