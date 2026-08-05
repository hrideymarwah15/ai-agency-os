"""CEO proposal-review workflow — the SC3 proof: discover → propose → gate → decide.

Node order: discover (LeadHunter, MOCK_MODE-gated) → propose (CEOAgent LLM review
with injected client) → prepare_request (queue row + approval_requested audit,
runs ONCE before the gate) → gate (interrupt) → proceed | cancel (decision audit
+ final status — Pitfall 1: side effects only ever run post-resume).

Audit placement rule (Pitfall 1): the approval_requested audit lives in the
run-once prepare_request node, NEVER inside the gate node — the gate re-runs on
resume and would emit a duplicate row. The round-trip tests assert exact counts.
"""

from typing import Any, cast

import httpx
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from backend import database
from backend.agents.ceo import CEOAgent
from backend.config import settings
from backend.services.approvals import create_request, expires_at_default
from backend.services.audit import AuditService
from backend.workflows.approval_graph import (
    ApprovalState,
    approval_node,
    cancel_node,
    proceed_node,
)
from backend.workflows.lead_hunter_graph import build_discover_node


class CEOReviewState(ApprovalState):
    """State for a CEO review run: business + proposal context plus the gate trail."""

    business_context: dict[str, Any]
    proposal_context: dict[str, Any]
    review_note: str | None


async def _audit(state: CEOReviewState, *, action: str, payload: dict[str, Any]) -> None:
    """Record one system audit row on the run's correlation_id (D-07)."""
    session_maker = database.async_session_maker
    if session_maker is None:
        return
    proposal = state.get("proposal_context") or {}
    async with session_maker() as session:
        await AuditService.record(
            session,
            actor="system",
            action=action,
            entity_type="proposal",
            entity_id=str(proposal.get("proposal_id", "unknown")),
            payload=payload,
            correlation_id=state["correlation_id"],
        )
        await session.commit()


async def _discover_node(state: CEOReviewState) -> dict[str, Any]:
    """Run MOCK_MODE-gated lead discovery and audit the run (once per workflow)."""
    discover = build_discover_node()
    result = await discover(cast(dict[str, Any], state))
    leads: list[dict[str, Any]] = result.get("leads", [])
    await _audit(
        state,
        action="discovery_run",
        payload={"leads_discovered": result.get("leads_discovered", len(leads))},
    )
    lead = leads[0] if leads else (state.get("business_context") or {}).get("lead", {})
    return {"business_context": {**(state.get("business_context") or {}), "lead": lead}}


async def _propose_node(
    state: CEOReviewState, client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """CEO LLM proposal review — evidence is code-built, never LLM free text (T-03-01).

    The LLM output lands in review_note only; the gate payload and the audit
    evidence come from the structured proposal_context (Decimal→str amounts).
    """
    agent = CEOAgent("CEO")
    review = await agent.call_llm(
        agent.build_messages(
            "Proposal review: evaluate this proposal against the agency guardrails "
            "and return a recommendation. The owner decides at the approval gate."
        ),
        temperature=0.2,
        client=client,
    )
    proposal = state["proposal_context"]
    evidence = {
        "amount": str(proposal["amount"]),  # Decimal → str, never float (T-03-01)
        "entity_type": "proposal",
        "entity_id": str(proposal["proposal_id"]),
        "details": {
            "business_name": proposal.get("business_name"),
            "package_name": proposal.get("package_name"),
            "service_type": str(proposal.get("service_type", "")),
            "scope_summary": proposal.get("scope_summary"),
            "min_price": str(proposal.get("min_price", "")),
        },
    }
    await _audit(state, action="proposal_reviewed", payload=evidence)
    return {"review_note": review, "proposal_evidence": evidence}


async def _prepare_request_node(state: CEOReviewState, config: RunnableConfig) -> dict[str, Any]:
    """Build the structured gate payload, upsert the queue row, audit the request.

    Runs exactly once, BEFORE the gate (Pitfall 1) — the thread_id comes from
    the run config, never from any client input (T-03-02).
    """
    proposal = state["proposal_context"]
    thread_id = str(config["configurable"]["thread_id"])
    details: dict[str, Any] = {
        "action_type": "proposal_approval",
        "entity_type": "proposal",
        "entity_id": str(proposal["proposal_id"]),
        "entity": str(proposal.get("business_name", "Unknown business")),
        "amount": str(proposal["amount"]),
        "currency": settings.default_currency,
        "details": {
            "package_name": proposal.get("package_name"),
            "service_type": str(proposal.get("service_type", "")),
            "scope_summary": proposal.get("scope_summary"),
        },
    }
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        await create_request(
            session,
            action_type="proposal_approval",
            entity_type="proposal",
            entity_id=details["entity_id"],
            context=details,
            thread_id=thread_id,
            expires_at=expires_at_default(),
            correlation_id=state["correlation_id"],
        )
        await AuditService.record(
            session,
            actor="system",
            action="approval_requested",
            entity_type="proposal",
            entity_id=details["entity_id"],
            payload={
                "action_type": "proposal_approval",
                "thread_id": thread_id,
                "amount": details["amount"],
            },
            correlation_id=state["correlation_id"],
        )
        await session.commit()
    return {"action_details": details}


def build_ceo_review_graph(checkpointer: Any, client: httpx.AsyncClient | None = None) -> Any:
    """Compile the SC3 CEO review graph on the given checkpointer.

    client is injected into the propose node's LLM call (test hermeticity);
    prod leaves it None to use the shared process-lifetime client.
    """

    async def propose(state: CEOReviewState) -> dict[str, Any]:
        return await _propose_node(state, client)

    builder = StateGraph(CEOReviewState)
    builder.add_node("discover", _discover_node)
    builder.add_node("propose", propose)
    builder.add_node("prepare_request", _prepare_request_node)
    builder.add_node("gate", approval_node)
    builder.add_node("proceed", proceed_node)
    builder.add_node("cancel", cancel_node)
    builder.add_edge(START, "discover")
    builder.add_edge("discover", "propose")
    builder.add_edge("propose", "prepare_request")
    builder.add_edge("prepare_request", "gate")
    # gate routes via Command(goto=...) — no static edge out of the gate.
    builder.add_edge("proceed", END)
    builder.add_edge("cancel", END)
    return builder.compile(checkpointer=checkpointer)


def demo_start_state(correlation_id: str) -> dict[str, Any]:
    """Sample business/proposal context for the owner-facing demo trigger (SC3)."""
    from decimal import Decimal
    from uuid import uuid4

    return {
        "business_context": {
            "lead": {
                "business_name": "Apex Dental Clinic",
                "industry": "Healthcare",
                "location": "Mumbai",
                "website_url": "https://apex-dental.example.com",
                "priority_score": 85.0,
            }
        },
        "proposal_context": {
            "proposal_id": str(uuid4()),
            "business_name": "Apex Dental Clinic",
            "package_name": "Starter",
            "service_type": "WEBSITE",
            "amount": Decimal("100000.00"),
            "min_price": Decimal("80000.00"),
            "scope_summary": "5-page responsive website with online booking",
        },
        "correlation_id": correlation_id,
    }
