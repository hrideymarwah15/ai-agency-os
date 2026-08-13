"""Proposal assembly from persisted lead intelligence and deterministic pricing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import config
from backend.database import Audit, Business, Proposal, ProposalStatus, ServiceType, WebsiteAudit
from backend.services.audit import AuditService
from backend.services.pricing.engine import PricingEngine, PricingInput

from .templates import ComponentBlock, ProposalTemplateEngine, SECTION_ORDER


class ProposalData(BaseModel):
    """Validated input for a generated proposal."""

    model_config = ConfigDict(str_strip_whitespace=True)

    lead_id: UUID
    meeting_notes: str = Field(default="", max_length=10000)
    package_name: str | None = Field(default=None, max_length=100)
    service_type: str | None = None


def _service_type(value: str | None, opportunities: list[dict[str, Any]]) -> str:
    if value:
        return value.lower()
    hint = str(opportunities[0].get("service_type", "website")) if opportunities else "website"
    return hint.lower().replace("ai_chatbot", "chatbots").replace("internal_ai", "custom_ai")


def _package(service: str, explicit: str | None, opportunities: list[dict[str, Any]]) -> str:
    if explicit:
        return explicit
    for item in opportunities:
        if item.get("package_name"):
            return str(item["package_name"])
    defaults = {"website": "Starter", "automations": "Basic", "chatbots": "Starter", "custom_ai": "TimeAndMaterials"}
    return defaults.get(service, "Starter")


def _database_service_type(service: str) -> ServiceType:
    mapping = {
        "website": ServiceType.WEBSITE,
        "automations": ServiceType.AUTOMATION,
        "automation": ServiceType.AUTOMATION,
        "chatbots": ServiceType.AI_CHATBOT,
        "chatbot": ServiceType.AI_CHATBOT,
        "custom_ai": ServiceType.INTERNAL_AI,
    }
    return mapping.get(service, ServiceType.WEBSITE)


class ProposalGenerator:
    """Build a proposal without committing it, so workers and API calls own transactions."""

    def __init__(self, templates: ProposalTemplateEngine | None = None) -> None:
        self.templates = templates or ProposalTemplateEngine()
        self.pricing = PricingEngine()

    async def generate(self, session: AsyncSession, data: ProposalData) -> Proposal:
        """Load lead context, compute pricing, render ten sections, and return a draft."""
        started = perf_counter()
        lead = await session.get(Business, data.lead_id)
        if lead is None:
            raise ValueError(f"Lead {data.lead_id} not found")
        audit = (
            await session.execute(
                select(WebsiteAudit)
                .where(WebsiteAudit.business_id == data.lead_id)
                .order_by(WebsiteAudit.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        legacy_audit = (
            await session.execute(
                select(Audit).where(Audit.business_id == data.lead_id).order_by(Audit.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()

        opportunities = list(lead.opportunities or [])
        service = _service_type(data.service_type, opportunities)
        package = _package(service, data.package_name, opportunities)
        hours = max(1.0, sum(float(item.get("estimated_hours", item.get("hours", 8))) for item in opportunities[:10]) or 20.0)
        complexity = min(5.0, max(1.0, float(opportunities[0].get("complexity", 2)) if opportunities else 2.0))
        pricing_output = self.pricing.compute(
            PricingInput(
                hours=hours,
                complexity=complexity,
                market_rate=float(lead.estimated_budget or 50000),
                competition=3.0,
                industry=lead.industry or "Other",
                size="Small" if (lead.employee_count or 0) < 50 else "Medium",
                expected_roi=50.0,
                historical_close_rate=0.2,
                package_name=package,
                service_type=service,
            )
        )
        now = datetime.now(UTC)
        expires = now + timedelta(days=14)
        audit_data = (
            {"performance_score": audit.performance_score, "accessibility_score": audit.accessibility_score,
             "seo_score": audit.seo_score, "mobile_score": audit.mobile_score, "cwv": audit.cwv,
             "tech_stack": audit.tech_stack, "gaps": audit.gaps}
            if audit else
            {"performance_score": legacy_audit.performance_score if legacy_audit else None,
             "accessibility_score": legacy_audit.accessibility_score if legacy_audit else None,
             "seo_score": legacy_audit.seo_score if legacy_audit else None,
             "mobile_score": None, "cwv": legacy_audit.core_web_vitals if legacy_audit else {},
             "tech_stack": [], "gaps": legacy_audit.missing_features if legacy_audit else []}
        )
        pricing = {**pricing_output.model_dump(), "package_name": package,
                   "line_items": [{"name": item.get("title", item.get("name", "Delivery")), "amount": pricing_output.recommended_price} for item in opportunities[:1]]}
        scope = {"deliverables": [item.get("title", item.get("name", "Configured delivery")) for item in opportunities] or [f"{package} implementation"],
                 "milestones": [], "acceptance_criteria": ["Agreed scope delivered and reviewed"], "out_of_scope": ["Unlisted integrations"]}
        timeline = {"phases": [{"name": "Discovery and delivery", "weeks": 2, "dependencies": []}], "dependencies": [], "total_weeks": 2, "buffer_weeks": 1}
        context: dict[str, Any] = {
            "lead": {"name": lead.name, "industry": lead.industry or "", "pain_points": lead.pain_points or [], "website_url": lead.website_url or ""},
            "audit": audit_data, "opportunities": opportunities, "pricing": pricing, "pricing_output": pricing_output.model_dump(),
            "scope": scope, "timeline": timeline, "faqs": [{"question": "How do we start?", "answer": "Approve the proposal and we will confirm kickoff.", "category": "process"}],
            "testimonials": [], "terms": {"payment_terms": "50% upfront, 50% on acceptance", "ip_clause": "Client receives project IP after final payment", "liability_cap": "Fees paid", "termination": "Written notice", "jurisdiction": "Applicable local law"},
            "next_steps": {"cta": "Approve this proposal to schedule kickoff.", "expires_at": expires.date().isoformat(), "contact_info": config.settings.agency_owner_email, "meeting_link": ""},
            "executive_summary": f"{lead.name} can address its current priorities with a focused {package} engagement.",
            "meeting_notes": data.meeting_notes,
            "service_type": service, "agency_brand": {"name": config.settings.agency_name}, "owner": {"name": config.settings.agency_owner_name},
        }
        sections = {block.value: self.templates.render_component(block, context) for block in SECTION_ORDER}
        full_html = self.templates.render_full_proposal(context)
        proposal = Proposal(
            business_id=lead.id, package_name=package, service_type=_database_service_type(service),
            proposed_price=pricing_output.recommended_price, min_price=pricing_output.minimum_price,
            current_offered_price=pricing_output.recommended_price, recurring_monthly_fee=0,
            scope_summary=context["executive_summary"], detailed_scope=scope, status=ProposalStatus.DRAFT,
            executive_summary=context["executive_summary"], website_audit=audit_data, opportunity_analysis=opportunities,
            scope_of_work=scope, timeline=timeline, pricing=pricing, faqs=context["faqs"], testimonials=[], terms=context["terms"],
            next_steps=context["next_steps"], full_html=full_html, section_html=sections, meeting_notes=data.meeting_notes,
            final_price=pricing_output.recommended_price, expires_at=expires,
            generation_time_ms=int((perf_counter() - started) * 1000),
        )
        session.add(proposal)
        await session.flush()
        await AuditService.record(session, actor="system", action="proposal.generate", entity_type="proposal", entity_id=str(proposal.id),
                                  correlation_id=str(proposal.id), payload={"lead_id": str(lead.id), "package": package, "pricing": pricing, "meeting_notes_included": bool(data.meeting_notes)})
        return proposal

    async def regenerate_section(self, session: AsyncSession, proposal: Proposal, section: ComponentBlock | str, content: str) -> Proposal:
        """Replace one owner-editable section, retain its prior version, and audit the edit."""
        block = ComponentBlock(section)
        history = list(proposal.version_history or [])
        history.append({"version": proposal.version, "section": block.value, "content": proposal.section_html.get(block.value, "")})
        proposal.section_html = {**(proposal.section_html or {}), block.value: content}
        proposal.version += 1
        proposal.version_history = history
        proposal.full_html = self.templates.environment.get_template("base_proposal.j2").render(
            lead={"name": "Client"}, pricing=proposal.pricing or {}, service_type=proposal.service_type.value,
            agency_brand={"name": config.settings.agency_name}, sections=proposal.section_html,
            section_order=[item.value for item in SECTION_ORDER]
        )
        await AuditService.record(session, actor=config.settings.agency_owner_email, action="proposal.edit", entity_type="proposal", entity_id=str(proposal.id),
                                  correlation_id=str(proposal.id), payload={"version": proposal.version, "section": block.value})
        return proposal
