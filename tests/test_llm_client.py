"""LLM client tests — D-18 Gemini header fix, tenacity retry, injectable client, budget gate.

Never hits the network: every provider call goes through an injected
httpx.AsyncClient built on httpx.MockTransport.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import backend.agents.base as base_module
from backend.database import AuditLog

GEMINI_SUCCESS = {"candidates": [{"content": {"parts": [{"text": "gemini-ok"}]}}]}
OPENAI_SUCCESS = {"choices": [{"message": {"content": "openai-ok"}}]}


@pytest.fixture
def llm_session_maker(test_engine, monkeypatch):
    """Point the module-level session maker at the test DB (budget gate needs a session)."""
    import backend.database as db

    maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db, "async_session_maker", maker)
    return maker


@pytest.fixture
def skip_budget_gate(monkeypatch):
    """Neutralize the budget gate for pure dispatch/retry tests (gate tested separately)."""

    async def _noop_reserve(session, **kwargs) -> None:
        return None

    monkeypatch.setattr(base_module, "reserve_llm", _noop_reserve)


@pytest.fixture
def provider_keys(monkeypatch):
    """Force provider selection: set exactly the given keys, blank the others.

    A developer .env may carry real API keys — the openrouter key wins provider
    selection, so every dispatch test must blank the other two providers.
    """

    def _apply(**keys: str) -> None:
        for name in ("openrouter_api_key", "groq_api_key", "gemini_api_key"):
            monkeypatch.setattr(base_module.settings, name, keys.get(name, ""))

    return _apply


@pytest.fixture
def instant_retries(monkeypatch):
    """Make tenacity's async sleep a no-op so retry tests run instantly."""

    async def _no_sleep(seconds: float) -> None:
        return None

    import tenacity.asyncio as tenacity_asyncio

    monkeypatch.setattr(tenacity_asyncio, "_portable_async_sleep", _no_sleep)


def _agent(name="tester", model="model-x"):
    from backend.agents.base import LLMAgent

    class _TestAgent(LLMAgent):
        """Concrete LLMAgent (abstract base needs get_default_system_prompt)."""

        def get_default_system_prompt(self) -> str:
            return "test system prompt"

    return _TestAgent(name=name, model=model)


async def test_gemini_sends_api_key_header_not_url_query(
    monkeypatch, skip_budget_gate, llm_session_maker, provider_keys
):
    provider_keys(gemini_api_key="test-gemini-key")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=GEMINI_SUCCESS)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await _agent().call_llm([{"role": "user", "content": "hi"}], client=client)
    finally:
        await client.aclose()

    assert result == "gemini-ok"
    request = captured["request"]
    # D-18: key in header...
    assert request.headers.get("X-Goog-Api-Key") == "test-gemini-key"
    # ...and never in the URL query (httpx URL.query is bytes).
    assert "key=" not in request.url.query.decode()
    assert request.url.path == "/v1beta/models/model-x:generateContent"


async def test_openrouter_builds_url_and_auth_header(
    monkeypatch, skip_budget_gate, llm_session_maker, provider_keys
):
    provider_keys(openrouter_api_key="test-or-key")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=OPENAI_SUCCESS)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await _agent().call_llm([{"role": "user", "content": "hi"}], client=client)
    finally:
        await client.aclose()

    assert result == "openai-ok"
    request = captured["request"]
    assert str(request.url).startswith("https://openrouter.ai/api/v1/chat/completions")
    assert request.headers.get("Authorization") == "Bearer test-or-key"


async def test_groq_builds_url_and_auth_header(
    monkeypatch, skip_budget_gate, llm_session_maker, provider_keys
):
    provider_keys(groq_api_key="test-groq-key")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=OPENAI_SUCCESS)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await _agent().call_llm([{"role": "user", "content": "hi"}], client=client)
    finally:
        await client.aclose()

    assert result == "openai-ok"
    request = captured["request"]
    assert str(request.url).startswith("https://api.groq.com/openai/v1/chat/completions")
    assert request.headers.get("Authorization") == "Bearer test-groq-key"


async def test_429_retried_then_error_envelope(
    monkeypatch, skip_budget_gate, llm_session_maker, instant_retries, provider_keys
):
    provider_keys(groq_api_key="test-groq-key")
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(429, json={"error": "rate limited"}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await _agent().call_llm([{"role": "user", "content": "hi"}], client=client)
    finally:
        await client.aclose()

    assert attempts["count"] == 3  # tenacity stop_after_attempt(3)
    assert result.startswith("ERROR:")


async def test_success_path_returns_parsed_content(
    monkeypatch, skip_budget_gate, llm_session_maker, provider_keys
):
    provider_keys(openrouter_api_key="test-or-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=OPENAI_SUCCESS)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await _agent().call_llm([{"role": "user", "content": "hi"}], client=client)
    finally:
        await client.aclose()

    assert result == "openai-ok"


async def test_network_error_returns_error_envelope(
    monkeypatch, skip_budget_gate, llm_session_maker, instant_retries, provider_keys
):
    provider_keys(openrouter_api_key="test-or-key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await _agent().call_llm([{"role": "user", "content": "hi"}], client=client)
    finally:
        await client.aclose()

    assert result.startswith("ERROR:")


async def test_budget_breach_never_contacts_provider(
    monkeypatch, llm_session_maker, instant_retries, provider_keys
):
    """Gate breach → ERROR envelope, budget_blocked audit row, zero network calls."""
    from decimal import Decimal

    from backend.database import LLMSpend

    provider_keys(groq_api_key="test-groq-key")
    # $0.01 budget → any call (min 1 cent estimate) exceeds it after the first reserve.
    monkeypatch.setattr(base_module.settings, "llm_daily_budget_usd_groq", Decimal("0.01"))
    # Unique model per run: audit_logs is append-only, so assertions must be scoped.
    model = f"breach-{uuid4().hex[:8]}"

    async with llm_session_maker() as session:
        await session.execute(delete(LLMSpend).where(LLMSpend.provider == "groq"))
        await session.commit()

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=OPENAI_SUCCESS)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await _agent(name="tester", model=model).call_llm(
            [{"role": "user", "content": "hi"}], client=client
        )
    finally:
        await client.aclose()

    assert result == "ERROR: budget exceeded"
    assert calls["count"] == 0  # provider never contacted

    async with llm_session_maker() as session:
        audit = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "budget_blocked",
                        AuditLog.payload["model"].astext == model,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(audit) == 1
    assert audit[0].entity_type == "llm_spend"
    assert audit[0].entity_id == "groq"
