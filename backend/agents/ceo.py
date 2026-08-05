"""CEO Agent - Strategic orchestration; approval authority lives in the graph gate.

D-10: the fake auto-approval branch and the string-keyword execute() dispatch
are gone. Proposal review is a graph node (ceo_graph.py) whose evidence feeds
the owner's approval gate — there is no auto-approval path left in this class.
"""

from typing import Any

from backend.agents.base import AgentContext, BaseAgent
from backend.config import settings


class CEOAgent(BaseAgent):
    """CEO Agent - High-level strategy, guardrails, and escalation handling."""

    def get_default_system_prompt(self) -> str:
        return f"""You are the CEO Agent of {settings.agency_name}.
Your role is strategic orchestration, setting guardrails, and preparing evidence for decisions.

RESPONSIBILITIES:
1. Prepare proposal review evidence for the owner's approval gate
2. Set strategic direction for lead targeting and pricing
3. Handle escalations from Negotiation Agent (custom terms, excessive discounts)
4. Monitor agency KPIs: revenue, conversion, delivery quality
5. Make exceptions to standard pricing when strategically justified

GUARDRAILS YOU ENFORCE:
- Max discount without approval: {settings.max_discount_percentage}%
- Auto-approve threshold: ₹{settings.auto_approve_threshold:,.0f}
- Minimum prices per service tier (non-negotiable floors)
- Never approve custom legal terms without review
- Never promise features not in service catalog

DECISION FRAMEWORK:
- You never decide an approval yourself — the owner decides at the approval gate
- Prioritize long-term client value (LTV) over single-deal margin
- Favor recurring revenue (MRR) over one-time fees
- Escalate to human owner only for: legal disputes, >50% discount requests, strategic partnerships

Respond with structured JSON including: decision, reasoning, conditions, next_actions."""

    async def execute(self, task: str, context: AgentContext | None = None) -> dict[str, Any]:
        if context:
            self.set_context(context)

        # D-10: no keyword dispatch — gated decisions flow through the workflow
        # graph. This entry point serves generic strategic requests only.
        messages = self.build_messages(task)
        response = await self.call_llm(messages, temperature=0.3)

        return {"success": True, "data": {"response": response}, "raw": response}

    async def _handle_escalation(self, task: str, context: AgentContext) -> dict[str, Any]:
        """Handle escalation from negotiation agent."""
        messages = self.build_messages(f"""
        ESCALATION REVIEW:
        {task}

        Context: {context.metadata if context else "None"}

        Provide decision: APPROVE_EXCEPTION / REJECT / REQUIRE_HUMAN_OWNER
        Include reasoning and any conditions.
        """)
        response = await self.call_llm(messages, temperature=0.2)
        return {"success": True, "data": {"response": response}, "raw": response}

    async def _set_strategy(self, task: str, context: AgentContext) -> dict[str, Any]:
        """Set strategic direction."""
        messages = self.build_messages(f"""
        STRATEGIC DIRECTION REQUEST:
        {task}

        Current agency: {settings.agency_name}
        Target industries: {list(settings.industry_multipliers.keys())}
        Service catalog: {list(settings.service_catalog.keys())}

        Provide: target_focus, pricing_adjustments, outreach_strategy, resource_allocation
        """)
        response = await self.call_llm(messages, temperature=0.4)
        return {"success": True, "data": {"response": response}, "raw": response}

    async def _review_kpis(self, context: AgentContext) -> dict[str, Any]:
        """Review agency KPIs."""
        return {
            "success": True,
            "data": {
                "kpis": {
                    "leads_discovered_monthly": 0,
                    "proposals_sent": 0,
                    "conversion_rate": 0.0,
                    "avg_deal_value": 0.0,
                    "mrr": 0.0,
                    "delivery_time_avg_days": 0,
                },
                "alerts": [],
                "recommendations": [
                    "Increase lead discovery volume",
                    "Optimize proposal conversion",
                ],
            },
        }
