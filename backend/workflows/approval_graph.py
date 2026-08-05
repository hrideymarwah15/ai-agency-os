"""Generic LangGraph approval gate — RESEARCH Pattern 1: interrupt FIRST, side effects AFTER.

Hard rules honored here:
- Pitfall 1: interrupt() is the first call in the gate node and there is no
  side effect before it (the node re-runs from the top on resume). Side effects
  live only in proceed/cancel nodes, which run exactly once after resume.
- Pitfall 2: interrupt() is never wrapped in try/except — a pause is normal flow.
- No conditional skipping or while loops — routing is a Command(goto=...).
- Payloads are JSON-serializable (structured state, never LLM free text — T-03-01).
"""

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from backend import database
from backend.services.audit import AuditService


class ApprovalState(TypedDict):
    """State schema for the generic gate: structured action details + decision trail."""

    action_details: dict[str, Any]
    correlation_id: str
    status: str | None
    decision_reason: str | None
    decision_actor: str | None


def approval_node(state: ApprovalState) -> Command[Literal["proceed", "cancel"]]:
    """Pause at the gate with a structured payload; route by the resume decision.

    On resume this node restarts from the top: interrupt() yields the owner's
    payload and the Command routes to proceed (explicit approve) or cancel
    (anything else — deterministic reject, T-03-04).
    """
    decision = interrupt({"question": "Approve this action?", "details": state["action_details"]})
    payload = decision if isinstance(decision, dict) else {}
    reason = payload.get("reason")
    actor = payload.get("actor")
    return Command(
        goto="proceed" if payload.get("decision") == "approve" else "cancel",
        update={
            "decision_reason": reason if isinstance(reason, str) and reason else None,
            "decision_actor": actor if isinstance(actor, str) and actor else "owner",
        },
    )


async def _record_decision(state: ApprovalState, action: str) -> None:
    """Audit the decision once — only ever called from a post-resume node."""
    details = state.get("action_details") or {}
    session_maker = database.async_session_maker
    if session_maker is None:
        return
    async with session_maker() as session:
        await AuditService.record(
            session,
            actor=state.get("decision_actor") or "owner",
            action=action,
            entity_type=str(details.get("entity_type", "action")),
            entity_id=str(details.get("entity_id") or details.get("entity") or "unknown"),
            payload={
                "decision": action,
                "reason": state.get("decision_reason"),
                "action_type": details.get("action_type"),
            },
            correlation_id=state["correlation_id"],
        )
        await session.commit()


async def proceed_node(state: ApprovalState) -> dict[str, Any]:
    """Post-resume side effects for an approved decision (runs exactly once)."""
    await _record_decision(state, action="approved")
    return {"status": "approved"}


async def cancel_node(state: ApprovalState) -> dict[str, Any]:
    """Post-resume side effects for a rejected decision (runs exactly once)."""
    await _record_decision(state, action="rejected")
    return {"status": "rejected"}


def build_approval_graph(checkpointer: Any) -> Any:
    """Compile the generic gate graph: approval (interrupt) → proceed | cancel."""
    builder = StateGraph(ApprovalState)
    builder.add_node("approval", approval_node)
    builder.add_node("proceed", proceed_node)
    builder.add_node("cancel", cancel_node)
    builder.add_edge(START, "approval")
    builder.add_edge("proceed", END)
    builder.add_edge("cancel", END)
    return builder.compile(checkpointer=checkpointer)
