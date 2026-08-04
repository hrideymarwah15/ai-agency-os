---
phase: 01-foundation-orchestration-core
plan: 04
subsystem: orchestration
tags: [budget, scheduler, atomic-counters, tenacity, httpx, apscheduler, heartbeat, audit, fnd-06, fnd-07, d-11, d-12, d-18]

# Dependency graph
requires:
  - phase: 01-foundation-orchestration-core
    plan: 01
    provides: walking skeleton (config budget settings, LLMSpend/OutreachSpend/SchedulerHeartbeat models, lifespan with init_db → alembic → checkpointer), AuditService, pytest infra + test DB
  - phase: 01-foundation-orchestration-core
    plan: 02
    provides: append-only audit_logs trigger (live in the test DB during wave 2 — tests scoped around it)
provides:
  - FND-06 atomic hard budget caps: reserve_llm/reserve_outreach guarded INSERT..ON CONFLICT UPDATE (both write paths cap-guarded), BudgetExceededError, budget_blocked audit event, prune_spend_rows window reset
  - FND-07 heartbeat-monitored scheduler: write_heartbeat upsert, check_heartbeat_staleness, AsyncIOScheduler (30s heartbeat + 0h spend-prune jobs), EVENT_JOB_ERROR loguru alert
  - call_llm budget gate (D-11) at the single LLM door; D-18 Gemini X-Goog-Api-Key header fix; tenacity retry (429/5xx, exp backoff + jitter, 3 attempts); injectable httpx client test seam
  - 19-test suite (14 budget/llm + 5 scheduler) proving caps under concurrency and the alert path; live-boot verified scheduler
affects: [01-03 agents (base.py budget gate is now part of the agent contract), Phase 3 outreach send choke point (reserve_outreach call site), later phases reusing write_heartbeat/check_heartbeat_staleness]

# Tech tracking
tech-stack:
  added: [tenacity (retry on LLM provider HTTP errors), apscheduler AsyncIOScheduler (runtime dep already declared), pg_insert ON CONFLICT guarded UPDATE idiom]
  patterns:
    - single atomic statement with guarded WHERE on EVERY write path: INSERT..SELECT..WHERE cost<=cap + ON CONFLICT DO UPDATE..WHERE existing+cost<=cap (never read-then-write — Pitfall 6/T-04-01)
    - AsyncSession.execute DML..RETURNING returns ChunkedIteratorResult (no .rowcount) → scalar_one_or_none() as the success signal
    - budget gate acquires its own session via database.async_session_maker — callers of call_llm need no session
    - tenacity retry_if_exception on httpx.HTTPStatusError (429, 500, 502, 503, 504), wait_random_exponential(0.5, 8), stop_after_attempt(3), reraise=True
    - injectable-client seam: client: httpx.AsyncClient | None on call_llm + provider methods; lazy module-level shared client otherwise
    - heartbeat upsert via pg_insert ON CONFLICT (job_name) — race-safe idempotency; missing row counts as stale
    - short enqueue-only scheduler jobs (D-12/Pitfall 8): max_instances=1, coalesce=True, misfire_grace_time=60; EVENT_JOB_ERROR listener → logger.error
    - tests: httpx.MockTransport for zero-network LLM tests; monkeypatched tenacity.asyncio._portable_async_sleep for instant retries; loguru callable-sink capture (Message is a str subclass)

key-files:
  created:
    - backend/services/budget.py (BudgetExceededError, reserve_llm, reserve_outreach, prune_spend_rows)
    - backend/services/scheduler.py (write_heartbeat, check_heartbeat_staleness, build_scheduler, start_scheduler, _on_job_error listener)
    - tests/test_budget.py (cap math, accumulate, hard-block+audit, asyncio.gather atomicity, outreach, prune)
    - tests/test_scheduler.py (upsert idempotency, staleness fresh/old/missing, job-error listener)
    - tests/test_llm_client.py (Gemini header D-18 regression, dispatch URLs/auth, 429 retry, success, network error, breach never contacts provider)
  modified:
    - backend/agents/base.py (call_llm budget gate + client seam + tenacity + D-18 header + E722/mypy fixes)
    - backend/main.py (lifespan: build_scheduler/start/write_heartbeat('startup')/shutdown between checkpointer and close_db)

decisions:
  - "Guarded INSERT..SELECT..WHERE + ON CONFLICT DO UPDATE..WHERE replaces the plain upsert-then-guard: a naive ON CONFLICT DO UPDATE guard leaves the FIRST insert unguarded (cap bypass proven by test) — both paths must carry the WHERE"
  - "Raw text SQL with CAST(:cost_cents AS integer) + gen_random_uuid()/NOW() instead of ORM pg_insert: the guarded-insert form has no ORM API and asyncpg rejects multi-use untyped params; ORM column defaults do not apply to raw DML"
  - "reserve_outreach is shipped with tests but has no call site yet — the send choke point lands with the Phase 3 outreach/send service (documented, not a stub)"
  - "BudgetExceededError returns the exact string 'ERROR: budget exceeded' (existing string-envelope convention)"
  - "apscheduler imports carry inline # type: ignore[import-untyped] (no py.typed in the lib; pyproject mypy config untouched)"

metrics:
  duration: ~55 min
  completed: 2026-08-05
  tests: 51 suite-green (22 baseline + 19 plan 01-04 + 10 plan 01-02 audit)
---

# Phase 01 Plan 04: Budget Caps and Heartbeat-Monitored Scheduler — Summary

**One-liner:** FND-06/FND-07 delivered — atomic hard budget caps for LLM spend (per-provider) and outreach volume with budget_blocked audit events, plus the call_llm gate completing D-18 (Gemini key in headers), tenacity retry, and the injectable httpx seam; and the heartbeat-monitored AsyncIOScheduler with staleness detection and EVENT_JOB_ERROR loguru alerts, wired into the app lifespan.

## What Was Built

### backend/services/budget.py (new)
- `BudgetExceededError(Exception)` carrying kind/key/cap/requested.
- `reserve_llm(session, *, provider, model, cost_cents)` and `reserve_outreach(session, *, channel)` — each is ONE atomic statement:
  `INSERT INTO … SELECT … WHERE cost <= cap ON CONFLICT … DO UPDATE SET … WHERE existing + cost <= cap RETURNING id`.
  Both write paths (first-ever call and every increment) are cap-guarded in the same statement — the only way to satisfy T-04-01 under concurrency.
- Zero rows returned ⇒ `AuditService.record(actor="system", action="budget_blocked", …)` + `BudgetExceededError` — the provider is never contacted (T-04-02, T-04-05).
- `prune_spend_rows(session, *, retention_days=30)` — bounded DELETE of counters older than retention (date-keyed counters self-reset daily).
- Commits its own transaction — the gate caller (`call_llm`) does not manage sessions.

### backend/agents/base.py (reworked — legacy file brought up to ruff/black/mypy clean)
1. **D-11 budget gate** inside `call_llm`, after provider selection, BEFORE the provider branch: estimated cost_cents from `llm_cost_usd_per_1k_tokens[provider] × max_tokens / 1000 × 100` (min 1 cent), reserved via `reserve_llm` on a session acquired from `database.async_session_maker`. Breach → `logger.error("[{name}] Budget exceeded: …")` → returns `"ERROR: budget exceeded"` (existing string-envelope convention).
2. **D-18 fix:** Gemini key moved from `?key=` URL query to the `X-Goog-Api-Key` header.
3. **Tenacity retry** on httpx.HTTPStatusError with status ∈ {429, 500, 502, 503, 504}, `wait_random_exponential(0.5, 8)`, `stop_after_attempt(3)`, `reraise=True` (research A1 — the documented 60s-no-retry defect).
4. **Injectable seam:** `call_llm(…, client: httpx.AsyncClient | None = None)` and all three `_call_*` methods accept an injected client; when None a lazy module-level shared client is used.
5. Repairs: bare `except:` → `except (ValueError, TypeError)`, missing annotations on `set_context`/`register_tool` (mypy clean), `return str(content)` to satisfy `no-any-return`.

### backend/services/scheduler.py (new)
- `write_heartbeat(session, *, job_name="heartbeat")` — pg_insert ON CONFLICT upsert (idempotent, race-safe).
- `check_heartbeat_staleness(session, *, threshold_seconds=120, job_names=("heartbeat",))` — names whose last beat is older than the threshold; a missing row counts as stale.
- `build_scheduler()` — AsyncIOScheduler(timezone="UTC") with heartbeat job (IntervalTrigger 30s) and spend-window-reset job (CronTrigger hour=0 → prune_spend_rows(30)); both `max_instances=1, coalesce=True, misfire_grace_time=60` (D-12/Pitfall 8 — short enqueue-only jobs); `add_listener(_on_job_error, EVENT_JOB_ERROR)` → loguru `[scheduler] job failed: …` alert.
- `start_scheduler()` helper for lifespan.

### backend/main.py (modified)
Lifespan order now: `init_db → alembic upgrade → checkpointer setup → build_scheduler/start → write_heartbeat("startup") → yield → scheduler.shutdown(wait=False) → close_db`. Live-verified: `/health` 200 and both `startup` + `heartbeat` rows present in Postgres within 38s of boot.

## Verification

- `uv run pytest tests/ -x -q` → **51 passed** (22 pre-existing + 10 from plan 01-02's audit suite + 19 from this plan).
- Atomicity test: 10 concurrent reserves at 25¢ against a 100¢ cap → exactly 4 succeed, 6 `BudgetExceededError`, `SUM(cost_cents) == 100` (zero overspend), `calls == 4`.
- Breach test: `"ERROR: budget exceeded"`, zero MockTransport calls (provider never contacted), one `budget_blocked` audit row.
- D-18 regression: Gemini request carries `X-Goog-Api-Key: test-gemini-key`; `"key=" not in request.url.query.decode()`; `grep -n "key=" backend/agents/base.py | grep -i gemini` → nothing.
- Retry: 429 handler → exactly 3 attempts → `ERROR:` envelope.
- Scheduler: two writes → one heartbeat row; fresh → `[]`; backdated/missing → `["heartbeat"]`; raising job → `[scheduler] job failed` in loguru capture.
- Live boot: uvicorn + `/health` 200 + `scheduler_heartbeats` rows (`startup` at boot, `heartbeat` at +30s).
- Gates: ruff + black + mypy clean on all plan-01-04 files (repo-wide ruff on `backend/` still flags pre-existing issues in `lead_hunter.py` — plan 01-03's file, deferred as instructed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] First-insert cap bypass — the guard must sit on BOTH write paths**
- **Found during:** Task 2 (breach test returned `openai-ok` — the provider was called despite a 1¢ cap)
- **Issue:** a plain `INSERT … ON CONFLICT DO UPDATE SET … WHERE cost+cost<=cap` only guards the UPDATE path; the first-ever INSERT for a (provider, model, date) key passed unconditionally, so a 40¢ first call sailed under a 1¢ cap (the exact T-04-01 bypass the plan guards against)
- **Fix:** rewrote both reserves as `INSERT … SELECT … WHERE cost<=cap ON CONFLICT DO UPDATE … WHERE existing+cost<=cap RETURNING id` — the guarded WHERE applies to the insert path AND the increment path, atomically
- **Files modified:** backend/services/budget.py
- **Commit:** 4689438

**2. [Rule 1 - Bug] AsyncSession DML..RETURNING has no rowcount**
- **Found during:** Task 2 first run — `AttributeError: 'ChunkedIteratorResult' object has no attribute 'rowcount'`
- **Fix:** use `result.scalar_one_or_none() is None` as the blocked signal (probe-verified on insert, guarded-update, and blocked paths); documented in code
- **Files modified:** backend/services/budget.py
- **Commit:** 4689438

**3. [Rule 1 - Bug] Raw DML bypasses ORM defaults and asyncpg param typing**
- **Found during:** Task 2 — `NotNullViolationError: null value in column "id"` (Python-side uuid4 default not applied to raw SQL); then `AmbiguousParameterError: inconsistent types deduced for parameter $4`
- **Fix:** explicit `gen_random_uuid()` + `NOW()` in the SELECT list; `CAST(:cost_cents AS integer)` on every param use
- **Files modified:** backend/services/budget.py
- **Commit:** 4689438

**4. [Rule 1 - Bug] Test isolation vs the live append-only audit trigger**
- **Found during:** Task 2 — the parallel plan-01-02 executor's audit migration (append-only trigger) landed in the test DB mid-wave; my fixtures' `DELETE FROM audit_logs` started raising `audit_logs is append-only`
- **Fix:** removed audit_logs deletes; audit assertions scoped by unique per-run keys (uuid4-suffixed model/channel) queried via JSONB `payload["model"].astext` filters — this also made the tests re-runnable (append-only rows accumulate across runs)
- **Files modified:** tests/test_budget.py, tests/test_llm_client.py
- **Commit:** 4689438

**5. [Rule 1 - Bug] .env API keys leaked into provider-selection tests**
- **Found during:** Task 2 — a developer `.env` carries a real OPENROUTER_API_KEY, so the openrouter branch always won; Gemini test hit the openrouter URL and the groq test hit openrouter too
- **Fix:** `provider_keys` fixture — blanks all three provider keys and sets exactly the one each test needs, patched on `backend.agents.base.settings` (the object base.py actually references — the conftest autouse fixture rebuilds the config singleton per test, so patching the test module's import is ineffective for lazily-imported modules)
- **Files modified:** tests/test_llm_client.py
- **Commit:** 4689438

**6. [Rule 1 - Bug] Test harness fixes (no product change)**
- `LLMAgent` is abstract (`get_default_system_prompt` unimplemented — pre-existing design) → tests use a concrete `_TestAgent` subclass
- loguru callable sinks receive `Message` (a `str` subclass), not dicts → substring assertion on the captured message
- httpx `URL.query` is bytes → `.decode()` before the `"key="` check
- **Files modified:** tests/test_llm_client.py, tests/test_scheduler.py
- **Commit:** 4689438 (partial), dae2f8c (scheduler test)

### Plan-driven adjustments (not bugs)
- `BudgetExceededError` returns the literal string `"ERROR: budget exceeded"` per the plan's envelope wording (the generic convention would have produced a different string).
- `check_heartbeat_staleness` takes a `job_names` tuple (default `("heartbeat",)`) so the missing-row-stale rule has a concrete scope.
- apscheduler is untyped → inline `# type: ignore[import-untyped]` on the four imports (pyproject mypy config untouched — not this plan's file).
- `write_heartbeat("startup")` in lifespan acquires its own session from `database.async_session_maker` (the plan's shorthand `await write_heartbeat("startup")` implies a session source).

## Decisions Made

1. **Guarded-both-paths atomic statement** — the invariant that makes concurrent overspend impossible (see Deviation 1).
2. **`scalar_one_or_none()` as the rowcount replacement** — driver-agnostic success signal for DML..RETURNING.
3. **Raw SQL for the guarded reserve** — no ORM API supports INSERT..SELECT..WHERE..ON CONFLICT; casts + gen_random_uuid make it driver-proof.
4. **reserve_outreach ships tested but uncalled** — the outreach send service lands in Phase 3; the cap is already enforced at the atomic level and ready to wire.
5. **Module-level shared LLM client** (lazy, process-lifetime) per the plan's seam wording; injected clients are never closed by provider methods.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: none | — | No surface beyond the plan's `<threat_model>`: no new endpoints, auth paths, or file access; the scheduler alert is log-based (loguru), the Gemini key moved OUT of URLs into headers, and the new writes (llm_spend/outreach_spend/scheduler_heartbeats/audit_logs budget_blocked) match the modeled trust boundaries. All T-04-01..05 mitigations implemented and tested. |

## Known Stubs

None. `reserve_outreach`'s call site is intentionally deferred to the Phase 3 send service (documented decision above — the atomic counter itself is complete and test-proven).

## Self-Check: PASSED

- [x] `backend/services/budget.py`, `backend/services/scheduler.py`, `backend/agents/base.py`, `backend/main.py`, `tests/test_budget.py`, `tests/test_scheduler.py`, `tests/test_llm_client.py` all exist
- [x] RED commit 1d01a23, GREEN commit 4689438, scheduler commit dae2f8c, docs commit 887c3c9 all present in git log
- [x] `uv run pytest tests/ -x -q` → 51 passed
- [x] ruff/black/mypy clean on all plan files
- [x] Live boot verified (uvicorn /health 200 + scheduler_heartbeats rows)
- [x] No modifications to STATE.md / ROADMAP.md
