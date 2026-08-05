"""LeadHunter discovery node factory — reusable LangGraph node over the agent.

The ceo_graph discover node composes this adapter; the agent's own
execute() string-keyword dispatch stays untouched for legacy callers
(CONTEXT §Integration Points — D-20 gates the mock data, not the wrapper).
"""

from collections.abc import Awaitable, Callable
from typing import Any

from backend.agents.lead_hunter import LeadHunterAgent

# LangGraph node signature: (state) -> state update (dict).
DiscoverNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def build_discover_node(agent: LeadHunterAgent | None = None) -> DiscoverNode:
    """Return a node that runs MOCK_MODE-gated discovery once per workflow run.

    The returned state update carries the discovered leads so the composing
    graph can audit (action="discovery_run") and enrich business context.
    """

    hunter = agent or LeadHunterAgent("LeadHunter")

    async def discover_node(state: dict[str, Any]) -> dict[str, Any]:
        result = await hunter._discover_leads("discover")
        data = result.get("data", {}) if result.get("success") else {}
        return {
            "leads": data.get("leads", []),
            "leads_discovered": data.get("leads_discovered", 0),
        }

    return discover_node
