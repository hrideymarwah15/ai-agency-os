"""SC3 capstone: the approval round-trip — pause → queue → approve/resume, reject/halt,
escalate, expiry — driven through the same code path the API uses (the approvals service).

The core round-trip tests (Task 2 scope) drive the approvals SERVICE directly with a
built graph; the API-level tests (Task 3 scope) exercise the TestClient surface
(302 + flash, 400 without reason, Origin 403, structured-only queue page) and the
scheduler registry. LLM calls are hermetic: service-level tests inject MockTransport,
API tests blank all provider keys so a developer .env can never leak real calls.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import conftest
import httpx
import pytest
from sqlalchemy import select, text

from backend.database import ApprovalRequest, ApprovalStatus, AuditLog

OPENAI_SUCCESS = {"choices": [{"message": {"content": "Proposal is within guardrails."}}]}


@pytest.fixture
async def clean_approval_tables(test_session):
    """Start every roundtrip test from empty approval/audit tables.

    TRUNCATE, not DELETE: plan 02's append-only trigger rejects DELETEs (T-02-01).
    """
    await test_session.execute(text("TRUNCATE approval_requests, audit_logs"))
    await test_session.commit()
    yield


@pytest.fixture
def app_session_maker(test_engine, monkeypatch):
    """Point the module-level session maker at the test engine (graph nodes + service)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    import backend.database as db

    maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db, "async_session_maker", maker)
    return maker


@pytest.fixture
def hermetic_llm(monkeypatch):
    """Blank all provider keys so no graph LLM call can reach the network.

    A developer .env may carry real API keys; blanking the live settings object
    (the one backend.agents.base holds) keeps every test call local.
    """
    import backend.agents.base as base_module

    for name in ("openrouter_api_key", "groq_api_key", "gemini_api_key"):
        monkeypatch.setattr(base_module.settings, name, "")


@pytest.fixture
def mock_llm(hermetic_llm, monkeypatch):
    """Route graph LLM calls to openrouter so the injected MockTransport answers them."""
    import backend.agents.base as base_module

    monkeypatch.setattr(base_module.settings, "openrouter_api_key", "test-or-key")


def _mock_llm_client(mock_transport, content: str = "Proposal is within guardrails."):
    """Build an httpx client whose MockTransport returns one canned LLM completion."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return mock_transport(handler)


def _initial_state(correlation_id: str) -> dict:
    """Sample business/proposal context for a demo gated proposal review (SC3)."""
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
            "proposal_id": str(uuid.uuid4()),
            "business_name": "Apex Dental Clinic",
            "package_name": "Starter",
            "service_type": "WEBSITE",
            "amount": Decimal("100000.00"),
            "min_price": Decimal("80000.00"),
            "scope_summary": "5-page responsive website with online booking",
        },
        "correlation_id": correlation_id,
    }


def _client():
    """TestClient with the app imported after the conftest test env is fixed."""
    from fastapi.testclient import TestClient

    from backend.main import app

    return TestClient(app, follow_redirects=False)


def _flash_message(response: httpx.Response) -> str:
    """UI-SPEC flash copy from the flash cookie.

    The flash cookie carries a percent-encoded JSON envelope: cookie values are
    ASCII-only on the wire (RFC 6265), so the copy's em-dash is JSON-escaped;
    unquote + json.loads restores the exact UI-SPEC text.
    """
    from urllib.parse import unquote

    raw = response.cookies.get("flash") or ""
    if not raw:
        return ""
    try:
        data = json.loads(unquote(raw))
    except ValueError:
        return unquote(raw)
    return data.get("message", "") if isinstance(data, dict) else raw


def _login(client):
    return client.post(
        "/auth/login",
        data={"email": "owner@test.local", "password": conftest.TEST_OWNER_PASSWORD},
    )


async def _audit_entries(test_session, correlation_id: str) -> list[AuditLog]:
    """The full audit trail for one correlation, in execution order (oldest first)."""
    result = await test_session.execute(
        select(AuditLog)
        .where(AuditLog.correlation_id == correlation_id)
        .order_by(AuditLog.created_at.asc())
    )
    return list(result.scalars().all())


# ── Task 2 scope: graph + approvals service round-trip ────────────────────


async def test_workflow_pauses_with_pending_row(
    app_session_maker,
    pg_saver,
    mock_transport,
    mock_llm,
    test_session,
    clean_approval_tables,
):
    """A gated run pauses at the interrupt gate with exactly one PENDING queue row."""
    from backend.workflows.ceo_graph import build_ceo_review_graph

    graph = build_ceo_review_graph(pg_saver, client=_mock_llm_client(mock_transport))
    thread_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    result = await graph.ainvoke(_initial_state(correlation_id), config=config)

    assert "__interrupt__" in result  # the gate paused; the interrupt was not swallowed
    rows = (await test_session.execute(select(ApprovalRequest))).scalars().all()
    assert len(rows) == 1  # upsert idempotency: exactly one row
    row = rows[0]
    assert row.status == ApprovalStatus.PENDING
    assert row.thread_id == thread_id
    assert len(row.thread_id) <= 255
    assert row.expires_at is not None  # T-03-06: expiry comes from settings
    assert row.action_type == "proposal_approval"
    assert row.entity_type == "proposal"
    # Structured gated context — amount is a string/Decimal, never a float (T-03-01).
    assert isinstance(row.context["amount"], str)
    Decimal(row.context["amount"])
    assert row.context["correlation_id"] == correlation_id


async def test_approve_resumes_and_completes(
    app_session_maker,
    pg_saver,
    mock_transport,
    mock_llm,
    test_session,
    clean_approval_tables,
):
    """Approve via the service: row flips APPROVED, the paused thread resumes to
    "approved", and the audit trail has exactly one approval_requested + one approved."""
    from backend.services.approvals import approve
    from backend.workflows.ceo_graph import build_ceo_review_graph

    graph = build_ceo_review_graph(pg_saver, client=_mock_llm_client(mock_transport))
    thread_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    await graph.ainvoke(_initial_state(correlation_id), config=config)
    row = (await test_session.execute(select(ApprovalRequest))).scalar_one()
    assert row.status == ApprovalStatus.PENDING

    decided = await approve(test_session, graph, row.id, reason="Looks good")

    assert decided.status == ApprovalStatus.APPROVED
    assert decided.decided_at is not None
    fresh = (
        await test_session.execute(select(ApprovalRequest).where(ApprovalRequest.id == row.id))
    ).scalar_one()
    await test_session.refresh(
        fresh
    )  # app commits via its own session — reload the stale identity-map entry
    assert fresh.status == ApprovalStatus.APPROVED

    # The resume completed the run: final graph state is "approved".
    snapshot = await graph.aget_state(config)
    assert snapshot.next == ()
    assert snapshot.values.get("status") == "approved"

    entries = await _audit_entries(test_session, correlation_id)
    actions = [e.action for e in entries]
    # Pitfall 1: the gate node never re-emits the pre-gate audit on resume.
    assert actions.count("approval_requested") == 1
    assert actions.count("approved") == 1
    for expected in ("discovery_run", "proposal_reviewed", "approval_requested", "approved"):
        assert expected in actions
    assert actions.index("approval_requested") < actions.index("approved")


async def test_reject_halts_with_reason(
    app_session_maker,
    pg_saver,
    mock_transport,
    mock_llm,
    test_session,
    clean_approval_tables,
):
    """Reject: row REJECTED with the reason persisted; the thread halts at "rejected";
    the decision is audited with the reason. An empty reason is refused."""
    import pytest as _pytest

    from backend.services.approvals import reject
    from backend.workflows.ceo_graph import build_ceo_review_graph

    graph = build_ceo_review_graph(pg_saver, client=_mock_llm_client(mock_transport))
    thread_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    await graph.ainvoke(_initial_state(correlation_id), config=config)
    row = (await test_session.execute(select(ApprovalRequest))).scalar_one()

    with _pytest.raises(ValueError):
        await reject(test_session, graph, row.id, reason="")

    decided = await reject(test_session, graph, row.id, reason="Budget does not fit")

    assert decided.status == ApprovalStatus.REJECTED
    assert decided.decision_reason == "Budget does not fit"
    fresh = (
        await test_session.execute(select(ApprovalRequest).where(ApprovalRequest.id == row.id))
    ).scalar_one()
    await test_session.refresh(
        fresh
    )  # app commits via its own session — reload the stale identity-map entry
    assert fresh.status == ApprovalStatus.REJECTED
    assert fresh.decision_reason == "Budget does not fit"

    snapshot = await graph.aget_state(config)
    assert snapshot.next == ()
    assert snapshot.values.get("status") == "rejected"

    entries = await _audit_entries(test_session, correlation_id)
    rejected = [e for e in entries if e.action == "rejected"]
    assert len(rejected) == 1
    assert rejected[0].payload.get("reason") == "Budget does not fit"
    assert [e.action for e in entries].count("approval_requested") == 1


async def test_escalate_flags_without_resume(
    app_session_maker,
    pg_saver,
    mock_transport,
    mock_llm,
    test_session,
    clean_approval_tables,
):
    """Escalate: row ESCALATED, audited, and the thread stays interrupted (no resume)."""
    from backend.services.approvals import escalate
    from backend.workflows.ceo_graph import build_ceo_review_graph

    graph = build_ceo_review_graph(pg_saver, client=_mock_llm_client(mock_transport))
    thread_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    await graph.ainvoke(_initial_state(correlation_id), config=config)
    row = (await test_session.execute(select(ApprovalRequest))).scalar_one()

    flagged = await escalate(test_session, row.id, reason="Needs legal review")

    assert flagged.status == ApprovalStatus.ESCALATED
    assert flagged.decision_reason == "Needs legal review"

    # No resume happened: the checkpoint still points at the interrupted gate node.
    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("gate",)
    assert snapshot.values.get("status") is None

    entries = await _audit_entries(test_session, correlation_id)
    escalated = [e for e in entries if e.action == "escalated"]
    assert len(escalated) == 1
    assert escalated[0].payload.get("reason") == "Needs legal review"


async def test_sweeper_expires_stale(
    app_session_maker,
    pg_saver,
    mock_transport,
    mock_llm,
    test_session,
    clean_approval_tables,
):
    """D-09: a PENDING row past expires_at is EXPIRED and its thread resumes as a
    reject with reason "timeout"; the expiry is audited."""
    from backend.services.approvals import expire_stale
    from backend.workflows.ceo_graph import build_ceo_review_graph

    graph = build_ceo_review_graph(pg_saver, client=_mock_llm_client(mock_transport))
    thread_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    await graph.ainvoke(_initial_state(correlation_id), config=config)
    row = (await test_session.execute(select(ApprovalRequest))).scalar_one()
    assert row.status == ApprovalStatus.PENDING

    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)  # backdate past expiry
    await test_session.commit()

    expired = await expire_stale(test_session, graph, datetime.now(UTC))
    assert [r.id for r in expired] == [row.id]

    fresh = (
        await test_session.execute(select(ApprovalRequest).where(ApprovalRequest.id == row.id))
    ).scalar_one()
    assert fresh.status == ApprovalStatus.EXPIRED
    assert fresh.decision_reason == "timeout"

    # The timeout reject resumed the thread to completion.
    snapshot = await graph.aget_state(config)
    assert snapshot.values.get("status") == "rejected"

    entries = await _audit_entries(test_session, correlation_id)
    expired_audits = [e for e in entries if e.action == "expired"]
    assert len(expired_audits) == 1
    assert expired_audits[0].payload.get("reason") == "timeout"


async def test_interrupt_not_swallowed(
    app_session_maker,
    pg_saver,
    mock_transport,
    mock_llm,
    test_session,
    clean_approval_tables,
):
    """T-03-04: the gate interrupt is never wrapped in try/except — the run pauses
    instead of erroring, and any non-approve resume routes to cancel deterministically."""
    from langgraph.types import Command

    from backend.workflows.ceo_graph import build_ceo_review_graph

    graph = build_ceo_review_graph(pg_saver, client=_mock_llm_client(mock_transport))
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(_initial_state(str(uuid.uuid4())), config=config)

    assert "__interrupt__" in result  # paused, not swallowed into an error envelope
    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("gate",)

    # A resume that is not an explicit approve must not proceed (deterministic routing).
    final = await graph.ainvoke(
        Command(resume={"decision": "maybe", "reason": "unsure"}), config=config
    )
    assert final.get("status") == "rejected"


# ── Task 3 scope: API surface (TestClient), queue page, sweeper registry ──


async def test_api_approve_returns_302_with_flash(
    migrated_db, test_session, hermetic_llm, clean_approval_tables
):
    """Owner approve from the queue: 302 + UI-SPEC flash; row APPROVED; audit intact."""
    with _client() as client:
        assert _login(client).status_code == 302
        assert client.post("/approvals/demo/start").status_code == 302

        row = (await test_session.execute(select(ApprovalRequest))).scalar_one()
        assert row.status == ApprovalStatus.PENDING
        correlation_id = row.context["correlation_id"]

        response = client.post(f"/approvals/{row.id}/approve")
        assert response.status_code == 302
        assert response.headers["location"] == "/approvals"
        assert "Approved — Apex Dental Clinic. The agent workflow has resumed." in _flash_message(
            response
        )

    fresh = (
        await test_session.execute(select(ApprovalRequest).where(ApprovalRequest.id == row.id))
    ).scalar_one()
    await test_session.refresh(
        fresh
    )  # app commits via its own session — reload the stale identity-map entry
    assert fresh.status == ApprovalStatus.APPROVED
    assert fresh.decided_at is not None

    entries = await _audit_entries(test_session, correlation_id)
    actions = [e.action for e in entries]
    assert actions.count("approval_requested") == 1
    assert actions.count("approved") == 1


async def test_api_reject_requires_reason_and_halts(
    migrated_db, test_session, hermetic_llm, clean_approval_tables
):
    """Reject without a reason → 400 re-render (row stays PENDING); with reason → 302,
    REJECTED, reason persisted, decision audited with the reason."""
    with _client() as client:
        assert _login(client).status_code == 302
        assert client.post("/approvals/demo/start").status_code == 302
        row = (await test_session.execute(select(ApprovalRequest))).scalar_one()
        correlation_id = row.context["correlation_id"]

        response = client.post(f"/approvals/{row.id}/reject")
        assert response.status_code == 400
        still = (
            await test_session.execute(select(ApprovalRequest).where(ApprovalRequest.id == row.id))
        ).scalar_one()
        assert still.status == ApprovalStatus.PENDING  # failed reject changed nothing

        response = client.post(
            f"/approvals/{row.id}/reject", data={"reason": "Budget does not fit"}
        )
        assert response.status_code == 302
        assert "Rejected — Apex Dental Clinic. The workflow has been halted." in _flash_message(
            response
        )

    fresh = (
        await test_session.execute(select(ApprovalRequest).where(ApprovalRequest.id == row.id))
    ).scalar_one()
    await test_session.refresh(
        fresh
    )  # app commits via its own session — reload the stale identity-map entry
    assert fresh.status == ApprovalStatus.REJECTED
    assert fresh.decision_reason == "Budget does not fit"

    entries = await _audit_entries(test_session, correlation_id)
    rejected = [e for e in entries if e.action == "rejected"]
    assert len(rejected) == 1
    assert rejected[0].payload.get("reason") == "Budget does not fit"


async def test_api_escalate_flags_row(
    migrated_db, test_session, hermetic_llm, clean_approval_tables
):
    """Escalate from the queue: 302 + UI-SPEC flash; row ESCALATED, no resume."""
    with _client() as client:
        assert _login(client).status_code == 302
        assert client.post("/approvals/demo/start").status_code == 302
        row = (await test_session.execute(select(ApprovalRequest))).scalar_one()

        response = client.post(f"/approvals/{row.id}/escalate")
        assert response.status_code == 302
        assert "Escalated — Apex Dental Clinic. Flagged for review." in _flash_message(response)

    fresh = (
        await test_session.execute(select(ApprovalRequest).where(ApprovalRequest.id == row.id))
    ).scalar_one()
    await test_session.refresh(
        fresh
    )  # app commits via its own session — reload the stale identity-map entry
    assert fresh.status == ApprovalStatus.ESCALATED


async def test_api_mismatched_origin_gets_403(
    migrated_db, test_session, hermetic_llm, clean_approval_tables
):
    """T-03-03 defense-in-depth: a cross-origin mutating POST is rejected with 403."""
    with _client() as client:
        assert _login(client).status_code == 302
        assert client.post("/approvals/demo/start").status_code == 302
        row = (await test_session.execute(select(ApprovalRequest))).scalar_one()

        response = client.post(
            f"/approvals/{row.id}/approve", headers={"origin": "https://evil.example"}
        )
        assert response.status_code == 403

    fresh = (
        await test_session.execute(select(ApprovalRequest).where(ApprovalRequest.id == row.id))
    ).scalar_one()
    await test_session.refresh(
        fresh
    )  # app commits via its own session — reload the stale identity-map entry
    assert fresh.status == ApprovalStatus.PENDING  # the action never ran


async def test_api_queue_page_renders_structured_fields_only(
    migrated_db, test_session, clean_approval_tables
):
    """T-03-01: the queue renders only code-built structured fields — a canary string
    planted in the context never reaches the page — and amounts format as 1,000.00."""
    from backend.services.approvals import create_request

    await create_request(
        test_session,
        action_type="proposal_approval",
        entity_type="proposal",
        entity_id="p-canary-1",
        context={
            "action_type": "proposal_approval",
            "amount": "1000.00",
            "currency": "₹",
            "entity": "Apex Dental Clinic",
            "entity_type": "proposal",
            "entity_id": "p-canary-1",
            "details": {"service": "Website Starter", "scope": "5-page responsive site"},
            "llm_prose": "CANARY_RAW_LLM_OUTPUT_9f2b",
        },
        thread_id=str(uuid.uuid4()),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        correlation_id=str(uuid.uuid4()),
    )

    with _client() as client:
        assert _login(client).status_code == 302
        response = client.get("/approvals")

    assert response.status_code == 200
    assert "CANARY_RAW_LLM_OUTPUT_9f2b" not in response.text  # raw LLM text never rendered
    assert "1,000.00" in response.text  # 2dp + thousands grouping — never "1000.0"
    assert "1000.0" not in response.text
    assert "Website Starter" in response.text
    assert "Pending" in response.text


def test_scheduler_registry_contains_approval_sweeper():
    """D-09: the app scheduler carries the approval sweeper (60s interval, coalesced)."""
    from apscheduler.triggers.interval import IntervalTrigger

    from backend.services.scheduler import build_scheduler

    scheduler = build_scheduler()
    job = scheduler.get_job("approval-sweeper")
    assert job is not None
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 60
    assert job.max_instances == 1
    assert job.coalesce is True
