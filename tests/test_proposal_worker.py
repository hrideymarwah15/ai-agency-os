"""Proposal delivery worker state, idempotency, and stale recovery tests."""

import asyncio
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.database import Business, BusinessStatus, OutboxEvent, Proposal, ProposalStatus, ServiceType, utc_now
from backend.services.proposal import worker


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return FakeScalars(self.values)


class FakeSession:
    def __init__(self, proposal, business, stale=None):
        self.proposal = proposal
        self.business = business
        self.stale = stale or []
        self.added = []

    async def get(self, model, identifier):
        if model is Proposal:
            return self.proposal
        if model is Business:
            return self.business
        return None

    async def execute(self, query):
        return FakeResult(self.stale)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        return None


def _delivery_objects():
    business = Business(id=uuid4(), name="Acme", email="client@example.com", status=BusinessStatus.CONTACTED)
    proposal = Proposal(id=uuid4(), business_id=business.id, package_name="Starter", service_type=ServiceType.WEBSITE, proposed_price=Decimal("50000"), min_price=Decimal("40000"), current_offered_price=Decimal("50000"), scope_summary="Scope", executive_summary="Summary", full_html="<p>Proposal</p>", status=ProposalStatus.DELIVERY_QUEUED, pricing={}, section_html={}, version_history=[])
    event = OutboxEvent(id=uuid4(), topic="proposal.deliver", payload={"proposal_id": str(proposal.id)}, status="IN_PROGRESS", attempts=1)
    return proposal, business, event


def test_delivery_transitions_only_after_provider_success(monkeypatch) -> None:
    proposal, business, event = _delivery_objects()
    session = FakeSession(proposal, business)
    calls = []

    class Client:
        async def send_email(self, **kwargs):
            calls.append(kwargs)
            return {"status": "sent"}

    monkeypatch.setattr(worker, "SendGridClient", Client)
    asyncio.run(worker._deliver(session, event))
    assert calls
    assert proposal.status == ProposalStatus.SENT
    assert business.status == BusinessStatus.NEGOTIATING
    audit = next(item for item in session.added if getattr(item, "action", None) == "proposal.sent")
    assert audit.correlation_id == str(proposal.id)


def test_delivery_is_idempotent_after_sent(monkeypatch) -> None:
    proposal, business, event = _delivery_objects()
    proposal.status = ProposalStatus.SENT
    session = FakeSession(proposal, business)
    class Client:
        def __init__(self):
            raise AssertionError("provider must not be called twice")
    monkeypatch.setattr(worker, "SendGridClient", Client)
    asyncio.run(worker._deliver(session, event))


def test_delivery_failure_leaves_business_and_proposal_queued(monkeypatch) -> None:
    proposal, business, event = _delivery_objects()
    session = FakeSession(proposal, business)

    class Client:
        async def send_email(self, **kwargs):
            raise RuntimeError("provider rejected")

    monkeypatch.setattr(worker, "SendGridClient", Client)
    with pytest.raises(RuntimeError, match="provider rejected"):
        asyncio.run(worker._deliver(session, event))
    assert proposal.status == ProposalStatus.DELIVERY_QUEUED
    assert business.status == BusinessStatus.CONTACTED
    assert not any(getattr(item, "action", None) == "proposal.sent" for item in session.added)


def test_stale_in_progress_event_is_requeued() -> None:
    proposal, business, event = _delivery_objects()
    event.next_run_at = utc_now() - timedelta(minutes=11)
    session = FakeSession(proposal, business, [event])
    asyncio.run(worker._recover_stale(session))
    assert event.status == "PENDING"
    assert "Recovered stale" in event.last_error
