# Testing Patterns

**Analysis Date:** 2026-08-04

## Test Framework

**Runner:**
- pytest `>=7.4.0` declared in `[project.optional-dependencies].dev` (`pyproject.toml:35`)
- pytest-asyncio `>=0.23.0` declared (`pyproject.toml:36`) for testing the async codebase
- pytest-cov `>=4.1.0` declared (`pyproject.toml:37`) for coverage
- **No test tooling is configured:** there is no `[tool.pytest.ini_options]` section in `pyproject.toml`, no `pytest.ini`, no `tox.ini`, no `setup.cfg`, no `conftest.py`, and no `[tool.coverage]` section anywhere
- Dev tools are not installed in the current environment (no `pytest`, `ruff`, `black`, or `mypy` binary/module available)

**Assertion Library:**
- pytest native `assert` (no third-party assertion library declared)

**Run Commands:**
```bash
# No commands are configured. There is no Makefile and no scripts/ content.
# Once dependencies are installed (pip install -e ".[dev]"), the expected commands are:
pytest                      # Run all tests (default discovery from repo root)
pytest --cov=backend        # Run with coverage against the backend package
pytest -m asyncio           # Async tests only (as configured, see below)
```

## Test File Organization

**Location:**
- `tests/` directory exists at the repository root but is **empty** — no test files, no `conftest.py`, no fixtures
- No tests are co-located with source; the repo-root `tests/` directory is the intended home

**Naming:**
- No test files exist, so no in-repo pattern is established. Use pytest defaults: `test_*.py` files in `tests/`, mirrored per source module: `tests/test_config.py`, `tests/test_database.py`, `tests/agents/test_base.py`, `tests/agents/test_ceo.py`, `tests/agents/test_lead_hunter.py`

**Structure:**
```
tests/
├── conftest.py                    # (create) shared fixtures: settings reset, db engine patches
├── test_config.py                 # Settings/env-var loading tests
├── test_database.py               # Enum/model definitions, session lifecycle
└── agents/
    ├── test_base.py               # AgentContext, BaseAgent dispatch, guardrails
    ├── test_ceo.py                # CEOAgent.execute dispatch and handlers
    └── test_lead_hunter.py        # LeadHunterAgent discovery/enrichment
```

## Test Structure

**Suite Organization:**
No suites exist. The natural structure for the current codebase is one test module per source module (mirroring `backend/` layout), using `describe`-style class grouping or flat `test_*` functions.

**Patterns (to establish, based on actual code):**
- Agent result assertions target the envelope dict: `assert result["success"] is True` and `assert "data" in result` — the envelope is produced at `backend/agents/base.py:168-172` and `backend/agents/ceo.py:54,64,85`
- `AgentContext` is constructed positionally/by keyword with `business_id`/`proposal_id`/`metadata` fields (`backend/agents/base.py:14-22`); `metadata: Dict[str, Any] = field(default_factory=dict)` requires `field` semantics — pass explicit dicts rather than relying on shared defaults
- Settings-dependent behavior reads module-level `settings` (`backend/config.py:183`) — reset via monkeypatch on `backend.config.settings` or by patching the imported reference in the module under test (e.g. `backend.agents.ceo.settings`)

## Mocking

**Framework:**
- No mocking framework is declared (no pytest-mock, no unittest.mock usage). Use stdlib `unittest.mock` (`monkeypatch` fixture, `Mock`, `AsyncMock`) until a framework is added

**Patterns (required by the current code):**
- Agent `execute()` dispatch is keyword-based on `task.lower()` (`backend/agents/ceo.py:41-48`, `backend/agents/lead_hunter.py:50-55`) — monkeypatch the private handlers (`_review_proposal`, `_discover_leads`) with `AsyncMock` to test dispatch logic
- `call_llm` branches on API keys (`backend/agents/base.py:56-63`) — set `settings.openrouter_api_key` etc. via monkeypatch, and patch `BaseAgent._call_openrouter`/`_call_groq`/`_call_gemini` with `AsyncMock` returning canned strings
- `LLMAgent.execute` JSON-parses LLM output by slicing between first `{` and last `}` (`backend/agents/base.py:162-170`) — feed malformed and well-formed JSON fixtures through `AsyncMock` to test both branches
- `database.py` uses module-level globals `engine`/`async_session_maker`/`supabase_client` (`backend/database.py:265-267`) — monkeypatch these globals directly; `init_db` conditionally creates the engine only `if settings.database_url` (`backend/database.py:275`) — test both the configured and unconfigured branches

**What to Mock:**
- All HTTP calls (httpx `AsyncClient`) — never hit OpenRouter/Groq/Gemini or Supabase from tests
- `settings` values that gate behavior (API keys, `database_url`, pricing guardrails)
- Private handler methods when testing dispatcher behavior

**What NOT to Mock:**
- Pure logic: `NegotiationAgent.check_guardrails` (`backend/agents/base.py:219-223`), `build_messages` history truncation (`backend/agents/base.py:127-135`), `enrich_business` field merging (`backend/agents/lead_hunter.py:129-144`)
- Pydantic `Settings` validation itself (test it against a controlled env via monkeypatch of environment variables, not mocks)

## Fixtures and Factories

**Test Data:**
- None exist. The codebase ships inline mock data that can seed fixtures: `mock_leads` in `LeadHunterAgent._discover_leads` (`backend/agents/lead_hunter.py:70-103`) and the `service_catalog`/`industry_multipliers` dicts in `backend/config.py:98-167`
- A `conftest.py` should define: a `settings` fixture that resets `backend.config.get_settings.cache_clear()` (the `@lru_cache()` at `backend/config.py:176` persists across tests otherwise), and an `agent_context` factory building `AgentContext(business_id=..., metadata={...})`

**Location:**
- `tests/conftest.py` for shared fixtures; per-module fixtures inside each test file

## Coverage

**Requirements:**
- None enforced — no `[tool.coverage]` configuration, no `--cov` invocation in any script, no CI pipeline exists (no `.github/`, no `.gitlab-ci.yml`, no other CI config anywhere in the repo)
- pytest-cov is declared in dev deps (`pyproject.toml:37`) but never configured or invoked

**View Coverage:**
```bash
pytest --cov=backend --cov-report=term-missing   # after installing dev deps
```

## Test Types

**Unit Tests:**
- None present. Natural targets: `Settings` env loading (`backend/config.py`), enum values (`backend/database.py:24-84`), `AgentContext` dataclass defaults (`backend/agents/base.py:14-22`), `check_guardrails` (`backend/agents/base.py:219-223`), `build_messages` truncation, `LLMAgent.execute` JSON extraction

**Integration Tests:**
- None present. Natural targets: `init_db`/`close_db`/`get_db` lifecycle (`backend/database.py:270-303`) against a test Postgres, and agent `execute` with mocked LLM but real context wiring

**E2E Tests:**
- Not used (no Playwright test config despite `playwright>=1.40.0` in `pyproject.toml:16`)

## Common Patterns

**Async Testing:**
- pytest-asyncio `>=0.23.0` is declared (`pyproject.toml:36`) but has no `asyncio_mode` setting — either add `asyncio_mode = "auto"` under a new `[tool.pytest.ini_options]` section or decorate tests explicitly with `@pytest.mark.asyncio`
- The codebase is async-first (`BaseAgent.execute`, `call_llm`, `init_db`, `get_db` are all `async def`), so nearly every agent test must be async

```python
# Pattern to establish (explicit marker until asyncio_mode is configured):
@pytest.mark.asyncio
async def test_execute_dispatch_approve_proposal(monkeypatch):
    from backend.agents.ceo import CEOAgent
    from backend.agents.base import AgentContext

    agent = CEOAgent("test-ceo")
    async def fake_review(context):
        return {"success": True, "data": {"decision": "APPROVED"}}
    monkeypatch.setattr(agent, "_review_proposal", fake_review)

    result = await agent.execute("approve_proposal", AgentContext(proposal_id="p1"))
    assert result["success"] is True
    assert result["data"]["decision"] == "APPROVED"
```

**Error Testing:**
```python
# Pattern to establish (LLM failure path returns error envelope, not exception):
@pytest.mark.asyncio
async def test_call_llm_returns_error_string_when_no_key(monkeypatch):
    from backend.agents.base import BaseAgent
    from backend.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")

    agent = BaseAgent("test-agent")
    result = await agent.call_llm([{"role": "user", "content": "hi"}])
    assert result == "ERROR: No LLM API key configured"  # backend/agents/base.py:63
```

**Settings isolation:**
- `get_settings` is `@lru_cache()`-memoized (`backend/config.py:176-179`) and `settings` is instantiated at import time (`backend/config.py:183`) — call `backend.config.get_settings.cache_clear()` in an autouse fixture so env-var monkeypatches apply, and always patch the imported reference (`backend.agents.ceo.settings`, `backend.agents.base.settings`) rather than `backend.config.settings` directly

---

*Testing analysis: 2026-08-04*
