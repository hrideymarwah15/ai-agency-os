"""Rule engine for automation and AI opportunities.

Loads YAML rule definitions, compiles simple detection predicates, and evaluates
against a Business + latest WebsiteAudit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.database import Business, WebsiteAudit

from .config import RulesConfig, load_rules


@dataclass
class Rule:
    name: str
    category: str  # "automation" or "ai"
    recommendation: str
    detection: dict[str, Any]
    roi_params: dict[str, Any]
    confidence: float

    def matches(self, business: Business, audit: WebsiteAudit | None) -> bool:
        """Return True if the audit/business satisfy the detection dict.

        Supported detection keys:
        - gaps_contains: list of gap kinds that must be present in audit.gaps
        - tech_stack_excludes: list of tech stack names that must NOT be present
        """
        if audit is None:
            return False
        # Helper to extract gaps kinds
        gaps = audit.gaps or []
        tech_stack = audit.tech_stack or []
        # Check gaps_contains
        gaps_required = self.detection.get("gaps_contains")
        if gaps_required and not any(gap.get("kind") in gaps_required for gap in gaps):
            return False
        # Check tech_stack_excludes
        excludes = self.detection.get("tech_stack_excludes")
        if excludes and any(ts.get("name") in excludes for ts in tech_stack):  # noqa: SIM103
            return False
        # Additional detection keys can be added later – default to True
        return True


class RuleEngine:
    def __init__(self, rules_path: str):
        self.rules_path = rules_path
        self._rules: list[Rule] = []
        self._load()

    def _load(self) -> None:
        cfg: RulesConfig = load_rules(self.rules_path)
        self._rules = []
        for rm in cfg.automation_rules:
            self._rules.append(
                Rule(
                    name=rm.name,
                    category=rm.category,
                    recommendation=rm.recommendation,
                    detection=rm.detection,
                    roi_params=rm.roi_params,
                    confidence=rm.confidence,
                )
            )
        for rm in cfg.ai_rules:
            self._rules.append(
                Rule(
                    name=rm.name,
                    category=rm.category,
                    recommendation=rm.recommendation,
                    detection=rm.detection,
                    roi_params=rm.roi_params,
                    confidence=rm.confidence,
                )
            )

    def evaluate_automation(self, business: Business, audit: WebsiteAudit | None) -> list[dict]:
        return [
            {
                "name": r.name,
                "category": r.category,
                "recommendation": r.recommendation,
                "roi_params": r.roi_params,
                "confidence": r.confidence,
            }
            for r in self._rules
            if r.category == "automation" and r.matches(business, audit)
        ]

    def evaluate_ai(self, business: Business, audit: WebsiteAudit | None) -> list[dict]:
        return [
            {
                "name": r.name,
                "category": r.category,
                "recommendation": r.recommendation,
                "roi_params": r.roi_params,
                "confidence": r.confidence,
            }
            for r in self._rules
            if r.category == "ai" and r.matches(business, audit)
        ]
