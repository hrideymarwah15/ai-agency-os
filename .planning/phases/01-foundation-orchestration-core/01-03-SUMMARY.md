---
phase: 01-foundation-orchestration-core
plan: 03
subsystem: api
tags: [langgraph, approvals, interrupt, queue, sweeper, postgres, testclient]

# Dependency graph
requires:
  - phase: 01-foundation-orchestration-core
    provides: auth session cookies, audit service, scheduler, CEO/LeadHunter agents, database models
provides:
  - Owner approval queue (PENDING-first / decided newest-first) with approve / reject-with-reason / escalate actions, Origin-checked 403 defense-in-depth
  - LangGraph interrupt-gate graphs (generic + CEO review) resuming on the row's own thread_id (v3 astream)
  - 60s approval sweeper expiring stale PENDING rows (48h default via APPROVAL_EXPIRY_SECONDS)
  - Demo trigger (MOCK_MODE-gated) producing a gated proposal review for manual UAT
affects: [02-frontend-workflows, contract-payment-gates, any downstream approval consumers]

# Tech tracking
tech-stack:
  added: [psycopg-backed langgraph AsyncPostgresSaver registry pattern]
  patterns:
    - "LangGraph v3 async resume: astream_events(Command(resume=...), version='v3') + await stream.output()"
    - "Registry singleton per event loop; saver's async context manager held alive by AsyncExitStack"
    - "Percent-encoded JSON flash cookie (RFC 6265 ASCII-safe, unquote+json.loads on read)"
    - "Queue evidence code-built only: str(Decimal) amounts, whitelisted detail labels, never raw LLM prose"
    - "interrupt() gate without try/except; Command(goto=...) resume routing; audit in proceed/cancel nodes"

key-files:
  created:
    - backend/services/approvals.py
    - backend/workflows/approval_graph.py
    - backend/workflows/ceo_graph.py
    - backend/workflows/lead_hunter_graph.py
    - backend/workflows/__init__.py
    - backend/api/approvals.py
    - backend/templates/approvals.html
  modified:
    - backend/agents/ceo.py
    - backend/agents/lead_hunter.py
    - backend/agents/base.py
    - backend/config.py
    - backend/auth/session.py
    - backend/api/auth.py
    - backend/main.py
    - backend/services/scheduler.py
    - backend/templates/base.html
    - backend/static/app.css
    - tests/test_approval_roundtrip.py
    - tests/test_auth.py

key-decisions:
  - "LangGraph v3 resume uses the ASYNC lane: astream_events(Command(resume=payload), version='v3') then await stream.output() — sync stream_events raises asyncio.InvalidStateError on AsyncPostgresSaver"
  - "Workflow registry is keyed by event loop id and keeps the saver's async context manager alive in an AsyncExitStack — dropping the CM garbage-collects the generator and closes the connection"
  - "Flash cookies carry a percent-encoded JSON envelope: RFC 6265 cookie values are ASCII-only, so the UI-SPEC copy (em-dash) round-trips via unquote + json.loads"
  - "Approval expiry defaults to 172800s (48h), swept every 60s by the APScheduler approval-sweeper job"
  - "Login landing page is /approvals per UI-SPEC (supersedes plan 01's /audit landing)"
  - "CEO/LeadHunter rework folded into the Task 2 commit: fake auto-approval branch and string-keyword execute dispatch removed; lead discovery gated on settings.mock_mode"

patterns-established:
  - "Gate payload and queue view evidence are code-built only — amount as str(Decimal), currency from settings, whitelisted detail labels; raw LLM prose never reaches the page"
  - "approve() commits the row flip BEFORE resuming the thread; re-running the demo upsert keeps exactly one PENDING row per thread_id"

requirements-completed: [FND-05, DASH-03, FND-04]

# Metrics
duration: 8h 36m
completed: 2026-08-05
---

# Phase 01 Plan 03: Owner Approval Queue Summary

**LangGraph interrupt-gate approval engine: paused CEO proposal reviews resume/approve/reject/escalate from an owner queue with code-built evidence, 60s stale-expiry sweeper, and UI-SPEC flash copy — proven end-to-end with the real CEO/LeadHunter agents (fake auto-approval removed, discovery MOCK_MODE-gated)**

## Performance

- **Duration:** 8h 36m (first plan commit 03:51 UTC → final 12:27 UTC)
- **Started:** 2026-08-05T03:51:36+05:30 (5708405)
- **Completed:** 2026-08-05T12:56:53+05:30 (3431ccf)
- **Tasks:** 3 (1 TDD RED + 2 implementation)
- **Files modified:** 19 (7 created, 12 modified)

## Accomplishments

- **Round-trip proven end-to-end:** demo gated review → PENDING row → approve → thread resumes on its own thread_id and completes (audited with correlation_id); reject halts with reason; escalate flags without resume; sweeper expires stale rows with `timeout` reason — all asserted by 12 round-trip tests plus the 86-test full suite
- **Queue surface per UI-SPEC:** PENDING-first (oldest first) then decided newest-first; structured-only view (`str(Decimal)` amounts, whitelisted labels, `₹` currency); approve / reject-with-mandatory-reason / escalate; Origin-check 403; nav badge with pending count; empty-state copy
- **Sweeper + registry:** APScheduler `approval-sweeper` job (60s, coalesce, misfire_grace 60) expires stale rows; per-loop registry shares one durable AsyncPostgresSaver between API and sweeper
- **Agent rework:** CEO fake auto-approval and string-keyword dispatch removed; LeadHunter `_discover_leads` gated on `settings.mock_mode` (live path via `build_compliant_client().fetch`); `AgentContext.correlation_id` added; `approval_expiry_seconds` config added

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing round-trip tests (RED)** - `5708405` (test)
2. **Task 2: Approvals service + interrupt-gate graphs (+ agent rework)** - `4f43793` (feat)
3. **Task 3: Owner approval queue API, page, sweeper wiring** - `3431ccf` (feat)

**Plan metadata:** `docs(01-03): complete approval engine plan` (hash in git log — this SUMMARY's own commit)

## Files Created/Modified

- `backend/services/approvals.py` - Queue CRUD (upsert-by-thread_id), ordering, approve/reject/escalate/expire_stale, `_resume` via v3 astream
- `backend/workflows/approval_graph.py` - Generic interrupt-gate graph (`ApprovalState`, interrupt-first gate, proceed/cancel nodes with audit)
- `backend/workflows/ceo_graph.py` - CEO review graph: discover → propose (hermetic-client injectable) → prepare_request → gate; `demo_start_state`
- `backend/workflows/lead_hunter_graph.py` - Discover node wrapping `LeadHunterAgent._discover_leads`
- `backend/workflows/__init__.py` - Per-loop registry holding saver CM in AsyncExitStack
- `backend/api/approvals.py` - Queue page + demo trigger + actions (Origin 403, reject-reason 400)
- `backend/templates/approvals.html` - Queue page (badges, details, forms, empty state)
- `backend/templates/base.html` - "Approval Queue" nav + pending-count badge
- `backend/static/app.css` - Queue/flash/nav-badge styles
- `backend/services/scheduler.py` - `approval-sweeper` job wiring
- `backend/main.py` - Router mount + login redirects to `/approvals`
- `backend/auth/session.py` - Percent-encoded JSON flash cookie
- `backend/api/auth.py` - Landing-page redirect change
- `backend/agents/{ceo,lead_hunter}.py`, `backend/agents/base.py` - Rework (no fake auto-approval, mock gating, `correlation_id`)
- `backend/config.py` - `APPROVAL_EXPIRY_SECONDS` (default 172800)
- `tests/test_approval_roundtrip.py` - 12 tests: service round-trip + API queue surface + sweeper registry
- `tests/test_auth.py` - Landing-page assertion updated to `/approvals`

## Decisions Made

- LangGraph v3 async-lane resume (`astream_events` + `await stream.output()`) — the sync `stream_events` API raises `asyncio.InvalidStateError` on an AsyncPostgresSaver (main-thread binding)
- Registry per event loop with the saver's async context manager pinned in an `AsyncExitStack` — a dropped CM garbage-collects the generator and closes the connection (this was the `psycopg.OperationalError: the connection is closed` root cause)
- Flash cookie = percent-encoded JSON envelope — RFC 6265 cookie values are ASCII-only on the wire; unquote + `json.loads` restores the exact UI-SPEC copy
- Sweeper policy: `expire_stale` rejects with explicit `timeout` reason, actor `system`; expiry from `settings.approval_expiry_seconds`
- Landing page after login: `/approvals` (UI-SPEC binding, supersedes plan 01's `/audit`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `psycopg.OperationalError: the connection is closed` in `AsyncPostgresSaver.setup()`**
- **Found during:** Task 3 (demo/start API test)
- **Issue:** `AsyncPostgresSaver.from_conn_string(dsn).__aenter__()` drops the temporary context manager; GC of the generator runs `aclose()`, closing the connection — flaky, appeared import-order-correlated while bisecting. The registry built a fresh saver per process after `backend.workflows.ceo_graph` was already imported (TestClient always does), so setup() always failed there.
- **Fix:** Registry holds the CM in a module-level `AsyncExitStack` and caches graphs per event-loop id (each TestClient portal loop and uvicorn's loop gets a loop-bound saver — `asyncio.Lock` inside the saver is loop-bound).
- **Files modified:** backend/workflows/__init__.py
- **Verification:** full round-trip suite + 86-test suite green
- **Committed in:** 3431ccf

**2. [Rule 1 - Bug] Flash cookie could not carry the UI-SPEC em-dash copy**
- **Found during:** Task 3 (flash assertion)
- **Issue:** Raw em-dash in `set_cookie` crashes starlette's latin-1 header encode; httpx 0.28 re-encodes headers ASCII and its cookie jar does not unquote — the test's raw-substring assertion was unsatisfiable via any cookie encoding.
- **Fix:** `set_flash` writes a percent-encoded JSON envelope (`quote(json.dumps(...))`); `read_flash` unquotes before parsing; test helper `_flash_message` mirrors it (unquote + `json.loads`). The exact UI-SPEC copy is asserted verbatim after round-trip.
- **Files modified:** backend/auth/session.py, tests/test_approval_roundtrip.py
- **Verification:** approve/reject/escalate flash assertions pass
- **Committed in:** 3431ccf

**3. [Rule 1 - Bug] `list_requests` generated invalid SQL**
- **Found during:** Task 3 (reject-400 and queue-page tests)
- **Issue:** `case(..., col.asc())` emitted `CASE WHEN ... THEN created_at ASC` — syntax error at or near "ASC" (asyncpg).
- **Fix:** Direction expressed via NULL placement: pending rows order by `created_at ASC NULLS LAST`, all rows tie-break by `created_at DESC`.
- **Files modified:** backend/services/approvals.py
- **Verification:** queue-page and reject tests green; full suite green
- **Committed in:** 3431ccf

**4. [Rule 1 - Bug] ORM identity-map staleness in API tests**
- **Found during:** Task 3 (approve/reject/escalate/403 status assertions)
- **Issue:** The app commits via its own sessions; `test_session` (expire_on_commit=False) kept returning the stale PENDING object — the DB was already APPROVED (verified via raw SQL). The 403 test could even false-pass on staleness.
- **Fix:** `await test_session.refresh(fresh)` before each post-client status assertion (4 tests).
- **Files modified:** tests/test_approval_roundtrip.py
- **Verification:** approve/reject/escalate/403 tests now assert real DB state
- **Committed in:** 3431ccf

**5. [Rule 1 - Bug] Plan 01 auth test asserted the superseded landing page**
- **Found during:** full-suite run
- **Issue:** `test_login_success_sets_session_cookie` expected the login redirect at `/audit`; plan 01-03's UI-SPEC makes `/approvals` the landing page.
- **Fix:** Assertion updated to `/approvals` with a comment citing UI-SPEC.
- **Files modified:** tests/test_auth.py
- **Verification:** full suite green
- **Committed in:** 3431ccf

---

**Total deviations:** 5 auto-fixed (all Rule 1 — correctness bugs in implementation or tests)
**Impact on plan:** All auto-fixes were necessary for the plan's acceptance criteria to hold. No scope creep.

## Issues Encountered

- The connection-closed bug masqueraded as an import-order problem (scripts failed only when `backend.workflows.ceo_graph` was imported before saver creation) — the real mechanism was GC of the dropped context manager; the import correlation was coincidence. Fixed by pinning the CM in an AsyncExitStack.
- Starlette 1.3.1 + httpx 0.28 cookie encoding constraints (latin-1 write, ASCII re-encode, no jar unquoting) forced the percent-encoded JSON envelope design; a naive `ensure_ascii=False` attempt crashed in starlette.
- Baseline noise only: `LangChainBetaWarning` (v3 streaming experimental) and `StarletteDeprecationWarning` (httpx vs httpx2) — no failures.

## User Setup Required

None - no external service configuration required. Demo trigger requires `MOCK_MODE=true` (the test env sets it; the production default gates the demo to 404).

## Next Phase Readiness

- The approval round-trip is fully green under the test env; manual UAT steps in PLAN §Verification are ready against a dev run (login → demo → approve/reject/escalate → sweeper).
- `approval_requests` table + `uq_approval_requests_thread_id` constraint exist via alembic migrations.
- Known follow-ups for later phases: an owner UI for viewing the audit trail (currently `/audit` page exists), phase-2 dashboard; approval queue pagination was deliberately not added (small volume).

---

*Phase: 01-foundation-orchestration-core*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 7 created files verified on disk; commits 5708405, 4f43793, 3431ccf verified in git log.
