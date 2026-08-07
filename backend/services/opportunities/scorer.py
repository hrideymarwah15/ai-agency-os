"""Lead scoring implementation for Phase 02.2.

Implements the 7‑factor weighted rubric described in the RESEARCH file. The
``score_lead`` method returns a tuple ``(score_0_100, tier, breakdown_list)``.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.database import Business, WebsiteAudit


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class ScoreBreakdown:
    factor: str
    weight_pct: int
    raw_score: int
    weighted_score: float
    signals_used: list[str]


# ---------------------------------------------------------------------------
# Default weighting – mirrors ``SCORING_WEIGHTS`` in the RESEARCH plan.
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS = {
    "website_quality": 0.20,
    "seo_maturity": 0.15,
    "growth_signals": 0.20,
    "company_size": 0.15,
    "automation_potential": 0.15,
    "ai_potential": 0.10,
    "budget_estimate": 0.05,
}


class LeadScorer:
    def __init__(self, weights: dict | None = None):
        self.weights = weights or DEFAULT_WEIGHTS

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def score_lead(
        self,
        business: Business,
        audit: WebsiteAudit | None,
        opportunities: list[dict] | None = None,
    ) -> tuple[int, str, list[ScoreBreakdown]]:
        """Score a lead and return (score, tier, breakdown).

        If there is no completed audit, the score is ``0`` and tier ``Raw``.
        """
        if audit is None or audit.status != "COMPLETED":
            # No data – return zero score.
            result = [
                ScoreBreakdown(factor, int(self.weights.get(factor, 0) * 100), 0, 0.0, ["no_audit"])
                for factor in self.weights
            ]
            return 0, "Raw", result

        opps = opportunities or []
        total = 0.0
        breakdown: list[ScoreBreakdown] = []
        for factor, weight in self.weights.items():
            raw = getattr(self, f"_score_{factor}")(business, audit, opps)
            weighted = raw * weight
            total += weighted
            breakdown.append(
                ScoreBreakdown(
                    factor=factor,
                    weight_pct=int(weight * 100),
                    raw_score=raw,
                    weighted_score=weighted,
                    signals_used=[],  # Simplified – could be filled with used signals
                )
            )
        score = max(0, min(100, round(total)))
        tier = self._tier(score)
        return score, tier, breakdown

    # ---------------------------------------------------------------------
    # Tier classification
    # ---------------------------------------------------------------------
    @staticmethod
    def _tier(score: int) -> str:
        if score >= 80:
            return "Hot"
        if score >= 60:
            return "Warm"
        if score >= 40:
            return "Cold"
        return "Raw"

    # ---------------------------------------------------------------------
    # Factor implementations – copied from RESEARCH description.
    # ---------------------------------------------------------------------
    @staticmethod
    def _score_website_quality(business: Business, audit: WebsiteAudit, opps: list[dict]) -> int:
        scores = [
            audit.performance_score,
            audit.accessibility_score,
            audit.seo_score,
            getattr(audit, "mobile_score", None),
        ]
        available = [s for s in scores if s is not None]
        return round(sum(available) / len(available)) if available else 0

    @staticmethod
    def _score_seo_maturity(business: Business, audit: WebsiteAudit, opps: list[dict]) -> int:
        base = audit.seo_score or 0
        seo_gaps = sum(
            1
            for g in (audit.gaps or [])
            if g.get("kind")
            in (
                "missing_cta",
                "no_direct_contact",
                "missing_contact_form",
            )
        )
        has_analytics = any(t.get("name") in ("ga4", "gtm", "ga") for t in (audit.analytics or []))
        return max(0, min(100, base - 10 * seo_gaps + (5 if has_analytics else 0)))

    @staticmethod
    def _score_growth_signals(business: Business, audit: WebsiteAudit, opps: list[dict]) -> int:
        score = 30
        for sig in business.growth_signals or []:
            if sig in ("hiring", "funding", "traffic_growth"):
                score += 15
            elif sig in ("social_growth", "new_location"):
                score += 10
        if business.rating and business.rating >= 4.0:
            score += 10
        if business.review_count and business.review_count > 50:
            score += 5
        return min(100, score)

    @staticmethod
    def _score_company_size(business: Business, audit: WebsiteAudit, opps: list[dict]) -> int:
        emp = business.employee_count or 0
        if 10 <= emp <= 200:
            return 100
        if emp < 10:
            return 60
        if emp <= 500:
            return 80
        return 70

    @staticmethod
    def _score_automation_potential(
        business: Business, audit: WebsiteAudit, opps: list[dict]
    ) -> int:
        auto_opps = [o for o in opps if o.get("category") == "automation"]
        manual_gaps = sum(
            1
            for g in (audit.gaps or [])
            if g.get("kind")
            in (
                "missing_contact_form",
                "form_no_action",
            )
        )
        return min(100, 30 + 15 * len(auto_opps) + 10 * manual_gaps)

    @staticmethod
    def _score_ai_potential(business: Business, audit: WebsiteAudit, opps: list[dict]) -> int:
        ai_opps = [o for o in opps if o.get("category") == "ai"]
        has_chatbot = any(
            t.get("name")
            in (
                "intercom",
                "drift",
                "crisp",
                "tawk",
                "freshchat",
            )
            for t in (audit.analytics or [])
        )
        has_crm = any(
            t.get("name")
            in (
                "hubspot",
                "salesforce",
                "pipedrive",
            )
            for t in (audit.analytics or [])
        )
        score = 20 + 20 * len(ai_opps)
        if not has_chatbot:
            score += 15
        if not has_crm:
            score += 10
        return min(100, score)

    @staticmethod
    def _score_budget_estimate(business: Business, audit: WebsiteAudit, opps: list[dict]) -> int:
        budget = business.estimated_budget or 0
        if budget >= 50000:
            return 100
        if budget >= 20000:
            return 70
        if budget >= 10000:
            return 50
        return 30
