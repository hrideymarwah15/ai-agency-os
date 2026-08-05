"""Approval queue service — CRUD for approval_requests + LangGraph resume orchestration.

Pitfall 7: this service reads/writes ONLY the approval_requests table (never
LangGraph internals). The graph's proceed/cancel nodes own the decision audits;
this service owns the row transitions and the resume commands (T-03-02: the
thread_id always comes from the row, never from a client).
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from langgraph.types import Command
from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import ApprovalRequest, ApprovalStatus, utc_now
from backend.services.audit import AuditService

# D-09: the sweeper rejects stale requests with this explicit reason (T-03-06).
TIMEOUT_REASON = "timeout"


async def create_request(
    session: AsyncSession,
    *,
    action_type: str,
    entity_type: str,
    entity_id: str | None,
    context: dict[str, Any],
    thread_id: str,
    expires_at: datetime,
    correlation_id: str,
) -> ApprovalRequest:
    """Insert a PENDING queue row, upserting by thread_id (idempotent on re-run).

    The correlation_id is folded into the stored context so every later action
    (escalate, expire, resume) can re-derive the audit trail for the run.
    """
    stored_context = {**context, "correlation_id": correlation_id}
    values = {
        "action_type": action_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "context": stored_context,
        "thread_id": thread_id,
        "status": ApprovalStatus.PENDING,
        "expires_at": expires_at,
    }
    stmt = (
        pg_insert(ApprovalRequest)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_approval_requests_thread_id",
            set_={"expires_at": expires_at, "status": ApprovalStatus.PENDING},
        )
    )
    await session.execute(stmt)
    await session.commit()
    row = (
        await session.execute(select(ApprovalRequest).where(ApprovalRequest.thread_id == thread_id))
    ).scalar_one()
    return row


async def list_requests(
    session: AsyncSession, status: ApprovalStatus | None = None
) -> Sequence[ApprovalRequest]:
    """Queue ordering (UI-SPEC): PENDING first, oldest first; decided newest-first."""
    stmt = select(ApprovalRequest)
    if status is not None:
        stmt = stmt.where(ApprovalRequest.status == status)
    stmt = stmt.order_by(
        case((ApprovalRequest.status == ApprovalStatus.PENDING, 0), else_=1),
        case(
            (ApprovalRequest.status == ApprovalStatus.PENDING, ApprovalRequest.created_at.asc()),
            else_=ApprovalRequest.created_at.desc(),
        ),
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_request(session: AsyncSession, request_id: UUID) -> ApprovalRequest:
    """Fetch one queue row, raising ValueError when it does not exist."""
    row = (
        await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == request_id))
    ).scalar_one_or_none()
    if row is None:
        raise ValueError(f"Approval request {request_id} not found")
    return row


def _resume_payload(decision: str, reason: str | None, actor: str) -> dict[str, str]:
    """Build the JSON-serializable Command(resume=...) payload for the gate."""
    return {"decision": decision, "reason": reason or "", "actor": actor}


async def _resume(
    graph: Any,
    row: ApprovalRequest,
    payload: dict[str, str],
) -> None:
    """Resume the paused thread on the row's OWN thread_id (T-03-02).

    v3 stream: `await run.output()` drives the run to completion and returns
    the final state; a re-paused run would surface on run.interrupted().
    """
    stream = await graph.astream_events(
        Command(resume=payload),
        config={"configurable": {"thread_id": str(row.thread_id)}},
        version="v3",
    )
    await stream.output()


async def approve(
    session: AsyncSession, graph: Any, request_id: UUID, reason: str = ""
) -> ApprovalRequest:
    """Flip the row APPROVED and resume the thread with an approve decision."""
    row = await get_request(session, request_id)
    if row.status != ApprovalStatus.PENDING:
        raise ValueError(f"Approval request {request_id} is not pending")
    if not row.thread_id:
        raise ValueError(f"Approval request {request_id} has no workflow thread")
    row.status = ApprovalStatus.APPROVED
    row.decided_at = utc_now()
    row.decision_reason = reason or None
    await session.commit()
    await _resume(graph, row, _resume_payload("approve", reason, actor="owner"))
    return row


async def reject(
    session: AsyncSession, graph: Any, request_id: UUID, reason: str
) -> ApprovalRequest:
    """Flip the row REJECTED and resume the thread with a reject decision.

    A reject without a reason is refused — the audit trail always records why.
    """
    if not reason or not reason.strip():
        raise ValueError("A reason is required to reject an approval request")
    row = await get_request(session, request_id)
    if row.status != ApprovalStatus.PENDING:
        raise ValueError(f"Approval request {request_id} is not pending")
    if not row.thread_id:
        raise ValueError(f"Approval request {request_id} has no workflow thread")
    row.status = ApprovalStatus.REJECTED
    row.decided_at = utc_now()
    row.decision_reason = reason.strip()
    await session.commit()
    await _resume(graph, row, _resume_payload("reject", reason.strip(), actor="owner"))
    return row


async def escalate(session: AsyncSession, request_id: UUID, reason: str) -> ApprovalRequest:
    """Flag the row ESCALATED without resuming the thread — the pause stays intact."""
    row = await get_request(session, request_id)
    if row.status != ApprovalStatus.PENDING:
        raise ValueError(f"Approval request {request_id} is not pending")
    row.status = ApprovalStatus.ESCALATED
    row.decided_at = utc_now()
    row.decision_reason = reason.strip() if reason else None
    await AuditService.record(
        session,
        actor="owner",
        action="escalated",
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        payload={"reason": row.decision_reason, "request_id": str(row.id)},
        correlation_id=row.context.get("correlation_id"),
    )
    await session.commit()
    return row


async def expire_stale(
    session: AsyncSession, graph: Any, now: datetime | None = None
) -> list[ApprovalRequest]:
    """D-09/T-03-06: auto-reject PENDING rows past expires_at with reason "timeout".

    Each expiry is an explicit, audited reject decision (actor="system") and
    resumes the paused thread so the workflow observes the timeout too.
    """
    moment = now or datetime.now(UTC)
    rows = (
        (
            await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.status == ApprovalStatus.PENDING,
                    ApprovalRequest.expires_at < moment,
                )
            )
        )
        .scalars()
        .all()
    )
    expired: list[ApprovalRequest] = []
    for row in rows:
        row.status = ApprovalStatus.EXPIRED
        row.decided_at = moment
        row.decision_reason = TIMEOUT_REASON
        await AuditService.record(
            session,
            actor="system",
            action="expired",
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            payload={"reason": TIMEOUT_REASON, "request_id": str(row.id)},
            correlation_id=row.context.get("correlation_id"),
        )
        await session.commit()
        if row.thread_id:
            await _resume(graph, row, _resume_payload("reject", TIMEOUT_REASON, actor="system"))
        expired.append(row)
    return expired


def expires_at_default() -> datetime:
    """T-03-06: the queue row expiry deadline comes from settings."""
    return datetime.now(UTC) + timedelta(seconds=settings.approval_expiry_seconds)
