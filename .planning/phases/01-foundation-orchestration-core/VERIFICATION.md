---
phase: 01-foundation-orchestration-core
verified: 2026-08-05T16:30:00Z
status: human_needed
score: 13/13 requirements verified (4/4 SC clusters verified programmatically)
overrides_applied: 0
gaps: []
human_verification:
  - test: "Visual review of the owner UI pages (login, audit log, approval queue, unsubscribe) for layout/design per UI-SPEC"
    expected: "Pages render cleanly with the slate/blue design tokens, badges, empty states, and flash messages"
    why_human: "Visual appearance and user flow completion cannot be verified by grep or unit tests"
  - test: "Manual UAT round-trip: boot with MOCK_MODE=true, log in, click 'Demo started', approve the gated proposal, and observe the workflow resume; then start a second demo and reject it with a reason"
    expected: "Approve shows 'The agent workflow has resumed' flash and the row moves to Approved; reject requires a reason and the row moves to Rejected"
    why_human: "Full browser-based user flow; unit tests use TestClient + mocked LLM transport"
  - test: "Live robots.txt behavior against a real domain (e.g., a site with a restrictive robots.txt) via build_compliant_client()"
    expected: "Denied paths raise RobotsDeniedError; allowed paths fetch; per-domain throttling observable"
    why_human: "External service interaction (live network + real robots.txt parsing)"
---

# Phase 1: Foundation & Orchestration Core — Verification Report

**Phase Goal (ROADMAP.md:27):** "The platform's plumbing is production-ready and the owner's trust mechanism works end-to-end: installable package, current declared dependencies, Alembic migrations, append-only audit log, hard budget caps, heartbeat-monitored scheduler, compliance middleware (robots.txt, per-domain rate limits, anti-spam caps, consent/suppression), session auth, and a LangGraph approval engine with an owner-facing approval queue that pauses and resumes agent workflows."

**Verified:** 2026-08-05
**Status:** human_needed (all programmatic checks PASS; visual/manual UAT items outstanding)
**Re-verification:** No — initial verification (no previous VERIFICATION.md existed)

**MVP-mode note:** ROADMAP marks Phase 1 `mode: mvp` but the phase goal is not in user-story form ("As a [role], I want to…"). Per `verify-mvp-mode.md` this is a goal-format discrepancy normally surfaced for `/gsd mvp-phase` reformatting. The orchestrator's explicit instruction for this run was requirements-based goal-backward verification, which was performed; a user-flow coverage table is included below in lieu of the MVP user-story framing.

## Goal Achievement

### Observable Truths (Success Criteria → Requirements)

| # | Requirement | Status | Evidence (file:line) |
|---|-------------|--------|----------------------|
| 1 | **FND-01** — Installable package, flat `backend/` layout, `__init__.py`, README | ✓ VERIFIED | `pyproject.toml:40-45` (setuptools `include = ["backend*"]`); 8 `__init__.py` files (backend, agents, api, auth, services, tools, workflows); `README.md` (install/run/migrate sections); `uv run python -c "import backend.main"` OK; live uvicorn boot on :8002 succeeded |
| 2 | **FND-02** — Current declared deps, `sqlalchemy` added, committed `uv.lock` | ✓ VERIFIED | `pyproject.toml:7-28` — fastapi>=0.141, langgraph 1.x (`>=1.2,<2` — legacy `0.0.30` pin gone), `sqlalchemy[asyncio]>=2.0.51,<2.1` added, httpx/supabase/redis current; `uv.lock` committed (git log `454f9a8`) |
| 3 | **FND-03** — Alembic migrations replace `create_all` | ✓ VERIFIED | `database.py:484` (init_db: "schema via Alembic, not create_all"); zero `create_all` in codebase; migrations `e565deca858e` (16 tables incl. audit_logs, approval_requests, llm_spend, outreach_spend, scheduler_heartbeats, consent_records, suppression_entries + `uq_approval_requests_thread_id`) and `0002` trigger; `uv run alembic check` → "No new upgrade operations detected."; migrations run in lifespan (`main.py:63-66`) |
| 4 | **FND-04** — Append-only audit log, correlation IDs, queryable | ✓ VERIFIED | `services/audit.py:16-37` (INSERT-only `record`, no update/delete methods — `test_no_update_or_delete_paths` introspects this); `query()` by correlation_id (`audit.py:40-53`); DB trigger `reject_audit_mutation` BEFORE UPDATE OR DELETE on audit_logs (`alembic/versions/0002_audit_append_only_trigger.py:24-35`); tamper tests against real Postgres (`tests/test_audit.py:130-178`); `/audit?correlation_id=` filter (`api/audit.py:21-36`, `templates/audit.html:8-12`); `ix_audit_logs_correlation_id` index |
| 5 | **FND-05** — Approval engine: view/approve/reject/escalate, resume/halt workflows | ✓ VERIFIED | `services/approvals.py` (upsert-by-thread create_request:53-66, PENDING-first list:69-87, approve:123-137, reject-with-reason:140-159, escalate:162-180, expire_stale:183-222); LangGraph interrupt gate `workflow/approval_graph.py:31-48` (interrupt-first, Command goto routing, no try/except); resume on the row's own thread_id (`approvals.py:105-120`); queue UI `api/approvals.py` + `templates/approvals.html`; sweeper job in `services/scheduler.py:82-93`; round-trip proven with real CEO/LeadHunter agents (`tests/test_approval_roundtrip.py:186-231` — approve resumes to final state "approved" with exact audit counts; reject halts:234; escalate:283; sweeper:318) |
| 6 | **FND-06** — Atomic hard budget caps (LLM + outreach) | ✓ VERIFIED | `services/budget.py:22-41` (guarded `INSERT…SELECT…WHERE cost<=cap ON CONFLICT DO UPDATE…WHERE existing+cost<=cap` on BOTH write paths — first-insert bypass eliminated); `BudgetExceededError` + `budget_blocked` audit (`budget.py:70-82`); gate wired into `agents/base.py:95-131` (`_reserve_budget` before provider contact — breach returns `"ERROR: budget exceeded"`, provider never contacted); concurrency test proves zero overspend (`tests/test_budget.py:89`); `reserve_outreach` shipped+tested (call site lands in Phase 3 send service — documented decision) |
| 7 | **FND-07** — Heartbeat-monitored scheduler with silent-failure alert | ✓ VERIFIED | `services/scheduler.py` — `write_heartbeat`/`check_heartbeat_staleness` (32-61), AsyncIOScheduler with 30s heartbeat + midnight spend-reset + 60s approval-sweeper jobs, all `max_instances=1, coalesce, misfire_grace 60` (101-129), `EVENT_JOB_ERROR` listener → loguru `[scheduler] job failed` (96-98); wired in lifespan `main.py:71-79`; **live-verified during this run**: booted uvicorn :8002 → `/health` 200 → `startup` + `heartbeat` rows present in `scheduler_heartbeats` |
| 8 | **CMP-01** — robots.txt deny-by-default before fetch | ✓ VERIFIED | `tools/http_client.py:37-44` (can_fetch gate raises `RobotsDeniedError` BEFORE any request); `services/compliance/robots.py` (per-domain TTL cache, any fetch/parse failure denies + audits `robots_denied_by_default`:55-82); tests `test_robots_deny_by_default_on_http_error/connection_error` + audit row test |
| 9 | **CMP-02** — Per-domain token-bucket rate limiting with jitter | ✓ VERIFIED | `services/compliance/rate_limit.py` (monotonic-clock token math, per-domain isolation, uniform jitter on every wait, refill=0 blocks forever); shared bucket across factories (`http_client.py:47-68`); tests incl. `test_bucket_domains_are_isolated`, jitter bounds |
| 10 | **CMP-03** — Anti-spam volume caps; blocked sends audited | ✓ VERIFIED | `services/compliance/send_gate.py:20-46` — `check_send` reserves via atomic `reserve_outreach` cap; every block writes `send_blocked` audit with reason (`consent_required\|suppressed\|daily_cap_exceeded\|address_required`); address check before cap reserve (blocked send never consumes a cap slot); tests |
| 11 | **CMP-04** — Consent records, suppression list, one-click unsubscribe | ✓ VERIFIED | `consent.py` (lawful_basis + source + ip + user_agent provenance), `suppression.py` (case-insensitive, `ON CONFLICT DO NOTHING` idempotent), `api/unsubscribe.py` (public GET, signed 7-day token IS the identity — no email param, `BadSignature`/`SignatureExpired` → invalid state with no DB write, 32-54), `templates/unsubscribe.html`; full round-trip test: unsubscribe → suppression row + audit → next `check_send` returns "suppressed" |
| 12 | **DASH-01** — Owner can log in with session auth | ✓ VERIFIED | `api/auth.py` (GET/POST /auth/login, POST /auth/logout; uniform "Invalid email or password."; Argon2id verify via pwdlib `PasswordHash.recommended()` in a thread:29,62-64); signed itsdangerous session cookie HttpOnly/SameSite=Lax/max_age=TTL (`auth/session.py:16-25`); 401 → 302 /auth/login flash redirect (`main.py:96-103`); login writes `owner_login` audit row with correlation_id (`auth.py:79-87`); auth tests green. Note: landing page after login is `/approvals` per UI-SPEC (the full pipeline dashboard is DASH-02, Phase 2 scope) |
| 13 | **DASH-03** — Review + act on audit entries and approval requests | ✓ VERIFIED | `/audit` read-only page with correlation filter (`api/audit.py:21-36`) + `/approvals` queue with PENDING-first ordering and approve/reject/escalate actions (`api/approvals.py:91-196`), both owner-guarded (`Depends(get_current_owner)`), Origin-checked 403 on mutating POSTs (`approvals.py:51-58`); queue renders code-built structured fields only, never raw LLM prose (`_DETAIL_LABELS` whitelist, `str(Decimal)` amounts — `approvals.py:61-88`) |

**Score:** 13/13 requirements verified programmatically.

### User Flow Coverage (owner-facing, per MVP framing)

| Step | Expected | Evidence | Status |
|------|----------|----------|--------|
| Open app | App boots; `/health` returns `{"status":"ok"}` with DB ping | `main.py:106-117`; live boot :8002 → 200 | ✓ |
| Log in | Owner email + Argon2id password → signed session cookie, redirected to approval queue | `api/auth.py:53-92`, `auth/session.py:16-25`; tests `test_auth.py` (cookie set, redirect to /approvals) | ✓ |
| Review audit log | Owner sees newest audit entries; correlation filter narrows to one trail; payloads escaped, correlation IDs never echoed | `api/audit.py:21-36`, `templates/audit.html`; tests (XSS escape, correlation secrecy, 401 redirect) | ✓ |
| Review approval queue | PENDING first (oldest first), decided newest-first; structured evidence only; pending-count nav badge | `services/approvals.py:69-87`, `api/approvals.py:70-115`, `templates/base.html:16-18`; queue tests | ✓ |
| Approve | Workflow resumes on its own thread and completes; row flips APPROVED; audited once | `services/approvals.py:123-137`; `tests/test_approval_roundtrip.py:186-231` (final state "approved", exact audit counts) | ✓ |
| Reject | Mandatory reason; workflow halts; row REJECTED; audited | `services/approvals.py:140-159`; `api/approvals.py:158-181` (400 re-render without reason); round-trip test | ✓ |
| Escalate | Row ESCALATED, thread stays paused, audited | `services/approvals.py:162-180`; round-trip test | ✓ |
| Unsubscribe (one click) | Signed 7-day token link removes recipient; tampered/expired token shows invalid state, no DB write | `api/unsubscribe.py:32-54`; suppression round-trip tests | ✓ |
| Outcome | "Owner's trust mechanism works end-to-end" — all five SC clusters true in code | SC1 install/run ✓, SC2 audit ✓, SC3 approval round-trip ✓, SC4 caps+heartbeat ✓, SC5 compliance ✓ | ✓ |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full test suite | `uv run pytest tests/ -q` | **86 passed** (3 benign warnings: LangChainBetaWarning v3 stream, StarletteDeprecationWarning) | ✓ PASS |
| Lint | `uv run ruff check backend/ tests/ scripts/` | "All checks passed!" | ✓ PASS |
| Type check | `uv run mypy backend/` | "Success: no issues found in 36 source files" | ✓ PASS |
| Format | `uv run black --check backend/ tests/ scripts/` | "47 files would be left unchanged" | ✓ PASS |
| Migration currency | `uv run alembic check` | "No new upgrade operations detected." | ✓ PASS |
| Package import | `uv run python -c "import backend.main"` | OK (flat-layout package resolvable) | ✓ PASS |
| App boot + health | `uv run uvicorn backend.main:app --port 8002` → `curl /health` | 200 `{"status":"ok"}` (DB ping through lifespan: init_db → alembic upgrade → checkpointer → scheduler → heartbeat) | ✓ PASS |
| Scheduler live | heartbeat rows in Postgres after boot | `startup` and `heartbeat` rows present and fresh in `scheduler_heartbeats` | ✓ PASS |
| Auth page | `curl /auth/login` | 200 (login page renders) | ✓ PASS |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `/audit` page | entries | `AuditService.list_recent/query` → `audit_logs` table (INSERT-only via audit trigger) | ✓ real DB rows (owner_login/logout, discovery_run, approval_*, budget_blocked, send_blocked, unsubscribed) | ✓ FLOWING |
| `/approvals` queue | rows | `approvals.list_requests` → `approval_requests` table (rows created by graph `prepare_request` node) | ✓ real DB rows from actual LangGraph runs | ✓ FLOWING |
| LLM gate | cost_cents | `_reserve_budget` → `reserve_llm` guarded atomic counter → `llm_spend` | ✓ atomic DB counter, hard-blocks with audit | ✓ FLOWING |
| Unsubscribe | suppression entry | signed token → `suppression.add` → `suppression_entries` | ✓ real DB write; next `check_send` sees it | ✓ FLOWING |
| Scheduler | heartbeats | `write_heartbeat` upsert → `scheduler_heartbeats` | ✓ live rows observed during boot | ✓ FLOWING |

### Key Link Verification

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| main.py lifespan | alembic upgrade + checkpointer + scheduler | `asyncio.to_thread(command.upgrade)` + `AsyncPostgresSaver` CM + `build_scheduler()` (`main.py:62-79`) | WIRED (live boot proven) |
| `call_llm` (agents/base.py) | `reserve_llm` budget gate | `_reserve_budget` before provider branch, `BudgetExceededError` → `"ERROR: budget exceeded"` (`base.py:95-131`) | WIRED |
| CEO review graph | approval queue row | `_prepare_request_node` → `create_request` (thread_id from run config, upsert-idempotent) + `approval_requested` audit (`ceo_graph.py:108-157`) | WIRED |
| Queue action | paused workflow resume | `approve/reject` → `_resume` → `astream_events(Command(resume=...))` on row's own thread_id (`approvals.py:105-136`) | WIRED (round-trip tests prove final state "approved") |
| Scheduler | sweeper/expiry | `_approval_sweeper_job` → `expire_stale` → reject with "timeout" + thread resume (`scheduler.py:82-93`, `approvals.py:183-222`) | WIRED (test_approval_roundtrip:318) |
| Compliant fetch door | robots + bucket | `CompliantHTTPClient.fetch`: can_fetch → acquire → GET (`http_client.py:37-44`) | WIRED |
| Send path | all four gates | `check_send`: consent → suppression → address → atomic cap reserve (`send_gate.py:20-32`) | WIRED (reserve_outreach call site here; actual send service is Phase 3) |
| `/unsubscribe` | suppression + audit | `suppression.add` + `AuditService.record("unsubscribed")` (`unsubscribe.py:44-53`) | WIRED |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
| ----------- | ----------- | ------ | -------- |
| FND-01 | Installable package + README | ✓ SATISFIED | pyproject packages, README, imports OK |
| FND-02 | Current deps + sqlalchemy + uv.lock | ✓ SATISFIED | pyproject.toml:7-28, uv.lock committed |
| FND-03 | Alembic migrations (no create_all) | ✓ SATISFIED | 2 revisions, alembic check clean, no create_all |
| FND-04 | Append-only audit + correlation | ✓ SATISFIED | AuditService + DB trigger + /audit filter |
| FND-05 | Approval queue + resume/halt | ✓ SATISFIED | approvals service + graphs + queue UI + round-trip tests |
| FND-06 | Hard budget caps | ✓ SATISFIED | guarded atomic counters + call_llm gate + concurrency proof |
| FND-07 | Heartbeat scheduler + alert | ✓ SATISFIED | scheduler.py + lifespan + live rows + error listener |
| CMP-01 | robots deny-by-default | ✓ SATISFIED | robots.py + RobotsDeniedError + tests |
| CMP-02 | Per-domain token bucket + jitter | ✓ SATISFIED | rate_limit.py + tests |
| CMP-03 | Anti-spam volume caps | ✓ SATISFIED | send_gate.py + atomic cap + audit |
| CMP-04 | Consent + suppression + unsubscribe | ✓ SATISFIED | consent/suppression/unsubscribe + round-trip tests |
| DASH-01 | Login with session auth | ✓ SATISFIED | Argon2id + signed cookie + owner guard |
| DASH-03 | Act on audit + approvals | ✓ SATISFIED | /audit + /approvals pages, owner-guarded, Origin 403 |

No orphaned requirements: all 13 roadmap-mapped Phase 1 requirements are claimed by the 5 plans and verified above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | none (no TBD/FIXME/XXX/PLACEHOLDER markers; no stub returns; no console.log; no hardcoded-empty data in render paths) | — | — |

No debt markers, no stub artifacts. `LeadHunterAgent._mock_leads` exists but is gated behind `settings.mock_mode` (dev-only, audited, documented D-20) — the live path routes through the compliant fetch door; real discovery sources are Phase 2 scope per ROADMAP.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | `reserve_outreach` call site (send choke point) | Phase 3 (Sales — outreach sequences) | ROADMAP Phase 3 goal: "compliant outreach sequences"; documented decision in 01-04 SUMMARY — the atomic cap itself is complete and test-proven |
| 2 | Real lead discovery sources (live path exists, sources land later) | Phase 2 (Discovery) | ROADMAP Phase 2 SC1: "runs collect candidates from 3-5 compliant sources" |

### Informational Notes (not gaps)

- **Dependency removals (FND-02):** legacy unused declarations `playwright`, `stripe`, `razorpay` were removed from `pyproject.toml` as part of the dependency repair (no Phase 1 call sites). They re-enter when their consumers land (crawler in Phase 2, payments in Phase 4) — consistent with the roadmap dependency, not a violation of FND-02 (which requires declared deps to be current — satisfied for everything declared).
- **DASH-01 "dashboard":** the owner's logged-in landing is `/approvals` per UI-SPEC; the `/audit` page is the second owner page. A literal pipeline dashboard is DASH-02 (Phase 2). The Phase 1 requirement (session-auth login) is fully met.

### Human Verification Required

1. **Visual review of the owner UI** — Log in and view the login page, audit log page (with a correlation filter applied), approval queue (with at least one PENDING row via the demo trigger), and the unsubscribe page. **Expected:** pages render per UI-SPEC (slate/blue palette, 400px cards, badges, empty states, flash messages). **Why human:** visual appearance and layout cannot be verified by code inspection.

2. **Manual UAT round-trip** — Boot with `MOCK_MODE=true` (dev `.env`), log in, click the demo trigger, approve the gated proposal review, and confirm the "workflow has resumed" flash + row state; start a second demo and reject with a reason (verify mandatory-reason behavior); escalate a third. **Expected:** approve resumes, reject halts, escalate flags — matching the automated round-trip tests but observed through the real browser session. **Why human:** unit tests use TestClient + mocked LLM transport; the browser flow with real LLM provider calls (or mock responses) is the SC3 end-user proof.

3. **Live robots.txt behavior** — Point `build_compliant_client()` at a real domain with a restrictive robots.txt and at one that fails to serve robots.txt. **Expected:** denied paths raise `RobotsDeniedError`; failures deny-by-default and audit when a session is provided. **Why human:** external network service interaction.

### Gaps Summary

**No gaps found.** All 13 Phase 1 requirements are genuinely implemented, wired, and data-flowing in the codebase — verified by code inspection (file:line evidence above), 86/86 passing tests, clean ruff/mypy/black/alembic gates, and a live app boot with scheduler heartbeat rows in Postgres. The phase goal's five success criteria are all observably true. The `human_needed` status reflects the three manual/visual items above, not any implementation deficiency.

---

_Verified: 2026-08-05_
_Verifier: the agent (gsd-verifier)_
