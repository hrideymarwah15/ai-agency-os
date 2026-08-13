"""Proposal template component and variant tests."""

import pytest

from backend.services.proposal.templates import ComponentBlock, ProposalTemplateEngine


@pytest.fixture
def context() -> dict:
    return {
        "lead": {"name": "Acme <script>", "pain_points": ["slow follow-up"]},
        "audit": {"performance_score": 60, "gaps": ["booking flow"]},
        "opportunities": [{"title": "Automate intake", "roi_monthly_inr": 25000}],
        "pricing": {"package_name": "Starter", "recommended_price": 50000, "line_items": [], "profit_margin_pct": 40, "max_discount_pct": 15},
        "scope": {"deliverables": ["Website"], "acceptance_criteria": ["Review"], "out_of_scope": ["Hosting"]},
        "timeline": {"phases": [{"name": "Delivery", "weeks": 2}], "buffer_weeks": 1, "total_weeks": 3},
        "faqs": [{"question": "Start?", "answer": "Approve."}], "testimonials": [],
        "terms": {"payment_terms": "50/50", "ip_clause": "On payment", "liability_cap": "Fees", "termination": "Notice", "jurisdiction": "Local"},
        "next_steps": {"cta": "Approve", "expires_at": "2026-08-27", "contact_info": "owner@test"},
        "executive_summary": "Focused delivery", "meeting_notes": "Notes", "service_type": "website", "agency_brand": {"name": "Agency"},
    }


def test_all_ten_sections_render_and_escape(context: dict) -> None:
    engine = ProposalTemplateEngine()
    rendered = {block: engine.render_component(block, context) for block in ComponentBlock}
    assert len(rendered) == 10
    assert all(value.strip() for value in rendered.values())
    assert "<script>" not in engine.render_full_proposal(context)
    assert engine.render_full_proposal(context).count('class="proposal-section"') == 10
    assert "No approved testimonials are included" in engine.render_full_proposal(context)


@pytest.mark.parametrize("service", ["website", "automations", "chatbot", "custom_ai"])
def test_service_variants_resolve(service: str, context: dict) -> None:
    context["service_type"] = service
    engine = ProposalTemplateEngine()
    expected_service = "automation" if service == "automations" else service
    for block in (ComponentBlock.SCOPE, ComponentBlock.TIMELINE, ComponentBlock.PRICING):
        assert engine.load_component(block, service).name == f"{expected_service}_{block.value}.j2"
