---
phase: 1
slug: foundation-orchestration-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (dev extras; `uv run pytest`) |
| **Config file** | `[tool.pytest.ini_options]` in pyproject.toml: `asyncio_mode = "auto"`, `asyncio_default_fixture_loop_scope = "function"`, `testpaths = ["tests"]` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest` (plus CI: `ruff` → `black --check` → `mypy` → `pytest`, D-19) |
| **Estimated runtime** | ~60 seconds |

Test DB: real PostgreSQL — dedicated database `ai_agency_os_test` (models use PGUUID → SQLite incompatible); schema created via Alembic upgrade head, not create_all. LangGraph tests: `InMemorySaver` for units; `AsyncPostgresSaver` for the round-trip integration test. LLM calls: `httpx.MockTransport` — zero network.

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| W0 | 01 | 0 | FND-01..07, CMP-01..04, DASH-01, DASH-03 | — | Test infra + fixtures | unit/integration | `uv run pytest tests/ -x -q` | ✅ / ❌ W0 | ⬜ pending |
| SC1 | 01 | 1 | FND-01, FND-02, FND-03 | — | Fresh-venv install + migrations | CI smoke + pytest fixture | CI job: fresh venv → `pip install -e .` → `alembic upgrade head` → uvicorn smoke → pytest | ❌ W0 | ⬜ pending |
| SC2 | 02 | 1 | DASH-01, FND-04 | T-01 / T-03 / T-06 | login cookie flags; 401 without session; append-only audit; correlation_id trail; tamper raises | unit + integration | `uv run pytest tests/test_auth.py tests/test_audit.py -x -q` | ❌ W0 | ⬜ pending |
| SC3 | 03 | 2 | FND-05, DASH-03 | T-09 | graph interrupts → PENDING row → approve resumes / reject halts; queue renders gated details | integration (PostgresSaver + TestClient) — capstone | `uv run pytest tests/test_approval_roundtrip.py -x -q` | ❌ W0 | ⬜ pending |
| SC4 | 04 | 2 | FND-06, FND-07 | T-04 | cap breach → BudgetExceededError + audit, provider never called; concurrent overspend blocked; heartbeat + staleness alert | unit | `uv run pytest tests/test_budget.py tests/test_scheduler.py -x -q` | ❌ W0 | ⬜ pending |
| SC5 | 05 | 2 | CMP-01..04 | — | robots deny-by-default; per-domain bucket + jitter; suppression/consent gates; unsubscribe blocks next send | unit + API integration | `uv run pytest tests/test_compliance.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures: settings with test env (`get_settings.cache_clear()` + env patch), async engine/session for `ai_agency_os_test`, Alembic upgrade fixture, InMemorySaver + AsyncPostgresSaver fixtures, MockTransport handler factory
- [ ] `tests/test_config.py` — config validation: required identity fields fail fast, alias mapping, placeholder rejection
- [ ] `tests/test_database.py` — DB lifecycle: get_db before init raises RuntimeError, URL creation with existing driver, tz-aware defaults, callable JSON defaults
- [ ] `tests/test_audit.py` — append-only service + trigger tamper test
- [ ] `tests/test_auth.py` — login/logout, cookie flags, expiry, tampered cookie 401
- [ ] `tests/test_budget.py` — cap math, atomicity under concurrency, breach audit
- [ ] `tests/test_scheduler.py` — heartbeat write + staleness detection + job-error listener
- [ ] `tests/test_compliance.py` — robots (allow/deny/parse-failure), token bucket + jitter, suppression/consent gates, unsubscribe
- [ ] `tests/test_approval_roundtrip.py` — SC3 capstone (graph + PostgresSaver + TestClient approve/reject/escalate)
- [ ] `tests/test_llm_client.py` — provider request building (Gemini key in header!), error paths, retry behavior
- [ ] Framework install: dev extras (`pytest`, `pytest-asyncio`, `pytest-cov`) via `uv add --dev`
- [ ] Postgres test database setup (Wave 0/1): create `ai_agency_os_test`, migrations in fixture

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fresh-venv `pip install -e .` from clean checkout | FND-01, FND-02 | Installer behavior outside test runtime | CI smoke job replicates it (fresh venv → install → upgrade → smoke) — CI is the gate |
| Startup migration on real Supabase (not local Postgres) | FND-03 | Requires Supabase project + credentials | Run `alembic upgrade head` against a scratch Supabase DB; confirm tables + audit trigger exist |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
