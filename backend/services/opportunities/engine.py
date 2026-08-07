"""Opportunity engine – rescoring leads after audit completion.

Provides :func:`rescore_lead` which fetches a Business and its latest completed
WebsiteAudit, runs the rule engine, ROI calculator and lead scorer, and upserts
the results onto the Business row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from backend import database
from backend.database import Business, WebsiteAudit

from .roi import ROICalculator
from .rules import RuleEngine
from .scorer import LeadScorer

# Path to the static rule YAML file – located alongside this module.
_RULES_PATH = Path(__file__).with_name("rules.yaml")


async def rescore_lead(session: database.AsyncSession, business_id: UUID) -> None:
    """Rescore a single lead and upsert opportunities and scoring.

    The function does **not** commit – the caller is responsible for committing
    (the outbox worker does this after marking the event DONE).
    """
    # Load business
    business = await session.get(Business, business_id)
    if not business:
        return

    # Load latest completed audit for this business
    audit = (
        await session.execute(
            select(WebsiteAudit)
            .where(WebsiteAudit.business_id == business_id, WebsiteAudit.status == "COMPLETED")
            .order_by(WebsiteAudit.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # Initialise components
    rule_engine = RuleEngine(str(_RULES_PATH))
    roi_calc = ROICalculator()
    scorer = LeadScorer()

    # Evaluate rules
    auto_opps = rule_engine.evaluate_automation(business, audit) if audit else []
    ai_opps = rule_engine.evaluate_ai(business, audit) if audit else []
    all_opps = auto_opps + ai_opps

    # Compute ROI for each opportunity and sort descending
    for opp in all_opps:
        opp["roi_monthly_inr"] = roi_calc.calc_roi(opp, business, audit)
    all_opps.sort(key=lambda o: o["roi_monthly_inr"], reverse=True)

    # Score the lead
    score, tier, breakdown = scorer.score_lead(business, audit, all_opps)

    # Upsert JSONB fields and scalar columns on Business
    business.opportunities = all_opps  # type: ignore[assignment]
    # Store a simple version counter for optimistic concurrency / future usage
    # opportunity_version tracking omitted
    business.priority_score = score  # type: ignore[assignment]
    business.tier = tier  # type: ignore[assignment]
    # Store breakdown as plain dicts for JSONB persistence
    business.score_breakdown = [b.__dict__ for b in breakdown]  # type: ignore[assignment]
    business.last_scored_at = datetime.now(UTC)  # type: ignore[assignment]
    # Also store total ROI for ordering in the queue (materialized column would be ideal)
    # total_roi tracking omitted

    # Record an audit log – optional but useful for traceability
    from backend.services.audit import AuditService

    await AuditService.record(
        session,
        actor="system",
        action="lead_rescored",
        entity_type="business",
        entity_id=str(business_id),
        payload={"score": score, "tier": tier, "opportunity_count": len(all_opps)},
    )
