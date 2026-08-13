"""Proposal generator structure and deterministic pricing integration tests."""

from decimal import Decimal
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.database import Business, ProposalStatus
from backend.services.proposal.generator import ProposalData, ProposalGenerator


class FakeResult:
    def scalar_one_or_none(self):
        return None


class FakeSession:
    def __init__(self, lead: Business) -> None:
        self.lead = lead
        self.added = []

    async def get(self, model, identifier):
        return self.lead

    async def execute(self, query):
        return FakeResult()

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid4()


@pytest.mark.parametrize(
    ("service", "package"),
    [("website", "Starter"), ("automations", "Basic"), ("chatbots", "Starter"), ("custom_ai", "TimeAndMaterials")],
)
def test_generate_populates_all_sections_and_pricing(service: str, package: str) -> None:
    lead = Business(id=uuid4(), name="Acme", industry="Technology", email="client@example.com", estimated_budget=Decimal("50000"), opportunities=[{"title": "Modernize", "service_type": service, "package_name": package, "estimated_hours": 20}])
    session = FakeSession(lead)
    proposal = asyncio.run(ProposalGenerator().generate(session, ProposalData(lead_id=lead.id, service_type=service, package_name=package, meeting_notes="Needs <b>a measurable</b> launch")))
    assert proposal.status == ProposalStatus.DRAFT
    assert proposal.package_name == package
    assert proposal.pricing["recommended_price"] > 0
    assert proposal.pricing["minimum_price"] > 0
    assert proposal.pricing["negotiation_limits"]
    assert all([proposal.executive_summary, proposal.website_audit is not None, proposal.opportunity_analysis, proposal.scope_of_work, proposal.timeline, proposal.pricing, proposal.faqs, proposal.terms, proposal.next_steps, proposal.full_html])
    assert len(proposal.section_html) == 10
    assert proposal.full_html.count('class="proposal-section"') == 10
    assert "No approved testimonials are included" in proposal.full_html
    assert "Needs &lt;b&gt;a measurable&lt;/b&gt; launch" in proposal.full_html
    assert "Needs <b>a measurable</b> launch" not in proposal.full_html
    assert any(getattr(item, "action", None) == "proposal.generate" for item in session.added)
    audit = next(item for item in session.added if getattr(item, "action", None) == "proposal.generate")
    assert audit.correlation_id == str(proposal.id)
