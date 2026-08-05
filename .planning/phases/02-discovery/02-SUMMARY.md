---
phase: 02-discovery
plan: 01
subsystem: discovery
tags: [postgres, outbox, asyncpg, sqlalchemy, httpx, robots, alembic, jinja2, apscheduler, tdd]

# Dependency graph
requires:
  - phase: 01-foundation-orchestration-core
    provides: auth/session (get_current_owner), AuditService (D-07 append-only), scheduler heartbeat (FND-07/D-12), approval/outbox patterns, config singleton
provides:
  - Full discovery pipeline: compliant ingestion (robots.txt + api_hosts exemption + token bucket), 5 source adapters + registry (hn/reddit/yelp/google_places/mock_directory), sanitizer (CMP-06), normalize + deterministic dedup, SSRF-safe enrichment, one-transaction run executor, durable outbox worker, daily enqueue-only scheduler job, owner-trigger endpoint, metrics/leads dashboard
affects: [03-audience-qualification, follow-on discovery phases, website-audit phase]

# Tech tracking
tech-stack:
  added: [none — zero new dependencies (stdlib html.parser/re/difflib/ipaddress/urllib)]
  patterns:
    - "Outbox enqueue + worker (D-12): trigger/scheduler only create run row + OutboxEvent; single asyncio worker executes serially"
    - "One run = one transaction (Pitfall 5): candidate inserts, lineage, per-source stats, run totals, audits commit together"
    - "Test seam: execute_run(run_id, *, client_factory) — production default builds the shared-bucket compliant client"
    - "RunContext carries the D-15 compliant client to adapters and enrichment alike"

key-files:
  created:
    - backend/services/discovery/base.py — SourceAdapter ABC, ParseError(RejectReason), SourceStatCollector, RunContext, SourceCandidate
    - backend/services/discovery/registry.py — ordered source registry with MOCK_MODE swapping and key gating
    - backend/services/discovery/sanitize.py — CMP-06 stdlib HTMLParser sanitizer with caps
    - backend/services/discovery/normalize.py — canonical dedup keys (domain/phone/email/name) + HN heuristics
    - backend/services/discovery/dedup.py — exact indexed lookups + fuzzy name pass (FUZZY_THRESHOLD 0.85) + fill-if-missing merge
    - backend/services/discovery/enricher.py — SSRF-validated homepage fetch (max 3 re-validated redirect hops), mailto/regex extraction
    - backend/services/discovery/runner.py — execute_run: collect → sanitize → normalize → dedup → enrich in one tx
    - backend/services/discovery/worker.py — outbox poller (IN_PROGRESS → DONE/FAILED), cancellation-clean
    - backend/services/discovery/sources/{hn,reddit,yelp,google_places,mock_directory}.py — live + Mock adapters
    - backend/alembic/versions/0003_discovery_schema.py — discovery_runs/run_source_stats/business_source_records + triggers
    - tests/test_discovery_{api,api_hosts,run,worker,registry,exclusion,sanitize,sources_hn,normalize,dedup,enricher}.py
    - tests/fixtures/hn_whoishiring_sample.json
  modified:
    - backend/database.py — DiscoveryRun/DiscoveryRunSourceStat/BusinessSourceRecord + RunStatus/SourceRunStatus
    - backend/config.py — discovery source flags + max items per source
    - backend/services/scheduler.py — daily enqueue-only discovery job
    - backend/main.py — lifespan starts/cancels the outbox worker
    - backend/api/discovery.py — trigger endpoint + full dashboard view model
    - backend/templates/discovery.html — runs table, expanders, leads table
    - backend/tools/http_client.py, backend/services/compliance/robots.py — api_hosts exemption
    - tests/conftest.py — discovery_db fixture

key-decisions:
  - "fetch_candidates declared as plain def returning AsyncIterator (not async def) because mypy rejects coroutine-returning overrides of async-generator implementations; subclasses are async generators with trailing bare yield after raise"
  - "runner.execute_run accepts an injectable client_factory test seam; production default is build_compliant_client(api_hosts=adapter.api_hosts, session=session)"
  - "run.total_candidates = Σ(new + merged) across sources (candidates that entered the business table this run)"
  - "BLOCKED sources (robots denial, 429/403 on first request, or ParseError(BLOCKED)) stop for the whole run and write a source_excluded audit (LEAD-04)"
  - "rejection bucket lines render count-desc/reason-asc because JSONB round-trips lose dict insertion order (Postgres sorts keys)"
  - "normalize_domain uses str.removeprefix('www.') — the RESEARCH sketch's removesuffix was wrong"
  - "worker tests no-op runner.enrich_homepage; run tests use a MockTransport fast-client factory so no test ever touches the real network"

patterns-established:
  - "TDD per task: RED test commit then GREEN feat commit (18 commits for 9 tasks)"
  - "test env: MOCK_MODE + fixed DATABASE_URL ai_agency_os_test; db_maker monkeypatches database.async_session_maker"
  - "identity-map staleness: tests expire_all()/re-select after the worker commits through its own session"

requirements-completed: [LEAD-01, LEAD-02, LEAD-03, LEAD-04, LEAD-05, DASH-02, CMP-06]

# Metrics
duration: 9h 20m
completed: 2026-08-05
---

# Phase 02 Discovery: Compliance-First Lead Discovery Pipeline

**Full discovery pipeline: robots-compliant collection (api_hosts exemption, token bucket), five source adapters + ordered registry, CMP-06 sanitizer, canonical-key dedup with deterministic fuzzy merge, SSRF-safe enrichment, one-transaction run executor, durable outbox worker, daily enqueue-only scheduler job, and a metrics/leads/lineage dashboard — 160 tests green with zero new dependencies**

## Performance

- **Duration:** 9h 20m
- **Started:** 2026-08-05T06:25:00Z (session start)
- **Completed:** 2026-08-05T15:45:00Z
- **Tasks:** 9 (all TDD: RED + GREEN commits)
- **Files modified:** 31

## Accomplishments
- Compliance gate first: `api_hosts` robots exemption (D-31) + shared token bucket; live sources (HN, Reddit, Yelp, Google Places) with `requires_keys` gating and mock substitutes in MOCK_MODE
- CMP-06 sanitizer (stdlib HTMLParser) with byte/text caps; structured-only view model (T-03-01) — no raw payloads or sanitized prose ever rendered
- Deterministic dedup: indexed canonical keys (domain/email/phone/name) + difflib fuzzy name pass at 0.85 with corroboration; fill-if-missing merge (FR-062); lineage via UNIQUE(source_id, source_item_id)
- SSRF-safe enrichment: URL validated before any fetch (private/link-local/ULA/userinfo/non-80-443 rejected), redirect hops re-validated and capped at 3, fill-if-missing only
- One-transaction run executor: candidate inserts, lineage, per-source stats, run totals and audits commit together — stats invariants asserted without sleeps (Pitfall 5)
- Durable outbox worker (serial drain, FAILED+last_error on exceptions, clean cancellation) wired into the app lifespan; daily `discovery-daily` scheduler job is enqueue-only (D-12)
- Dashboard: per-run per-source parsed/found cells, tfoot totals, dedup rate, server-formatted durations, rejection bucket lines, blocked/error visibility (LEAD-04), leads table with lineage badges and enrichment coverage
- Full suite grew from 89 to 160 tests; phase gate green (pytest/ruff/mypy) except the pre-existing `tests/test_database.py` black drift (deferred)

## Task Commits

Each task was committed atomically (TDD: `test` RED → `feat` GREEN):

1. **Task 01: api_hosts exemption** - `2a53893` (test), `6014e8e` (feat), `89a5ad5` (fix)
2. **Task 02: schema + config + migration** - `1513257` (feat, no separate RED — schema tests live in 01)
3. **Task 03: trigger + page skeleton** - `2c1b02d` (test), `0c9c910` (feat)
4. **Task 04: sanitize + fixtures** - `ab298ac` (test), `dcd9226` (feat)
5. **Task 05: adapters + registry** - `54e72d9` (test), `73e8135` (feat)
6. **Task 06: normalize + dedup + enrich** - `fc5426f` (test), `7307139` (feat)
7. **Task 07: runner + outbox worker** - `e77254a` (test), `bec60ba` (feat)
8. **Task 08: daily scheduler job** - `a68ff55` (test), `7bb1f4b` (feat)
9. **Task 09: dashboard metrics + leads** - `ab6ea5c` (test), `702d31e` (feat)

## Files Created/Modified

### Backend services
- `backend/services/discovery/base.py` — SourceAdapter contract, ParseError(reason, item_id), SourceStatCollector (requests/found/parsed/rejected + buckets), RunContext, SourceCandidate
- `backend/services/discovery/registry.py` — `all_sources()`/`enabled_sources()` in UI column order; MOCK_MODE class swap; key gating (D-21)
- `backend/services/discovery/sanitize.py` — CMP-06 HTML→text sanitizer (stdlib), 512KB/20KB caps
- `backend/services/discovery/normalize.py` — canonical domain/phone/email/name keys; `normalize_hn_job_post` heuristics
- `backend/services/discovery/dedup.py` — exact + fuzzy dedup, `ingest_candidate` → (master, NEW|MERGED|REUSED), fill-if-missing merge, `dedup_rate`
- `backend/services/discovery/enricher.py` — SSRF validation, redirect-peeling fetch (httpx 0.28 3xx handling), email/phone/form extraction
- `backend/services/discovery/runner.py` — `execute_run(run_id, *, client_factory=None)`; one commit per run
- `backend/services/discovery/worker.py` — `discovery_worker(poll_interval=5.0)`; PENDING → IN_PROGRESS → DONE/FAILED
- `backend/services/discovery/sources/{hn,reddit,yelp,google_places,mock_directory}.py` — live + mock adapters (ZERO requests when excluded)

### Wiring
- `backend/database.py` — 3 discovery models + 2 status enums (D-28, D-24, LEAD-05)
- `backend/config.py` — source flags, DISCOVERY_MAX_ITEMS_PER_SOURCE
- `backend/services/scheduler.py` — `_discovery_daily_job()` + `discovery-daily` registration
- `backend/main.py` — lifespan starts/cancels the worker
- `backend/api/discovery.py` + `backend/templates/discovery.html` — trigger + full dashboard
- `backend/alembic/versions/0003_discovery_schema.py` — schema + audit trigger + outbox index
- `backend/tools/http_client.py`, `backend/services/compliance/robots.py` — api_hosts exemption
- `tests/` — 11 discovery test files + fixture JSON; `conftest.py` discovery_db

## Decisions Made
- Plain-`def` `fetch_candidates` contract (mypy async-generator constraint); async-generator subclasses
- `client_factory` test seam on `execute_run`; production default reads `adapter.api_hosts`
- `total_candidates` = Σ(new+merged) per run; `dedup_rate = merged/(new+merged)` percent, "—" when none
- BLOCKED sources (RobotsDeniedError, HTTP 429/403, ParseError(BLOCKED)) stop for the run + `source_excluded` audit (LEAD-04)
- JSONB loses dict order → bucket lines sorted count-desc/reason-asc
- Enrichment runs in-run via the same compliant client (fill-if-missing only); tests no-op or mock it
- Worker test staleness: `expire_all()` before polling reads (identity-map gotcha)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MockTransport 429 test needed an async generator**
- **Found during:** Task 07 (RED)
- **Issue:** `def` + `yield` creates a sync generator; `async for` failed with "got generator"
- **Fix:** Declared the flaky/parse-error test adapters `async def` (matching the base contract)
- **Files modified:** tests/test_discovery_run.py
- **Verification:** 429 test passes (BLOCKED + source_excluded + PARTIAL)
- **Committed in:** e77254a (RED), bec60ba (GREEN)

**2. [Rule 1 - Bug] test_session identity map hid worker commits**
- **Found during:** Task 07 (worker tests)
- **Issue:** Worker commits through its own session; the test session's identity map returned stale PENDING instances forever — drain assertion timed out
- **Fix:** `expire_all()` before each polling SELECT; capture plain UUIDs before expiring (MissingGreenlet on sync attr access)
- **Files modified:** tests/test_discovery_worker.py
- **Verification:** 3 worker tests pass
- **Committed in:** bec60ba

**3. [Rule 1 - Bug] `await test_session.expire_all()` is invalid (sync API)**
- **Found during:** Task 07 (run tests)
- **Issue:** `TypeError: object NoneType can't be used in 'await' expression`; then MissingGreenlet when accessing expired attributes synchronously before an await
- **Fix:** Dropped the `await`; passed plain UUIDs into helpers after expiration
- **Files modified:** tests/test_discovery_run.py
- **Verification:** 5 run tests pass
- **Committed in:** bec60ba

**4. [Rule 1 - Bug] Worker test failed on leftover outbox events from other tests**
- **Found during:** Task 07 (worker tests)
- **Issue:** `discovery_db` only truncates discovery tables; stale `outbox_events` from earlier tests (incl. the T03 trigger test) broke drain assertions. Bonus: `audit_logs` is append-only (D-07 trigger) — DELETE is blocked by design
- **Fix:** Autouse `clean_outbox` fixture deletes outbox events only; audit_logs left alone
- **Files modified:** tests/test_discovery_worker.py
- **Verification:** worker suite green in full-suite runs
- **Committed in:** bec60ba

**5. [Rule 1 - Bug] enricher mypy: Returning Any from urljoin(action)**
- **Found during:** Task 06 (GREEN gates)
- **Issue:** `match.group(1)` is typed Any; `urljoin(base, Any)` → Any returned from `str | None` function (warn_return_any)
- **Fix:** Pinned `action: str = match.group(1)`
- **Files modified:** backend/services/discovery/enricher.py
- **Verification:** mypy clean
- **Committed in:** 7307139

**6. [Rule 1 - Bug] Dedup tests needed real DiscoveryRun rows (FK)**
- **Found during:** Task 06 (RED)
- **Issue:** `business_source_records.run_id` FK → `discovery_runs.id`; seeding with random UUIDs raised asyncpg ForeignKeyViolationError
- **Fix:** `_make_run(session)` helper creating a RUNNING DiscoveryRun; all six call sites updated
- **Files modified:** tests/test_discovery_dedup.py
- **Verification:** dedup suite green
- **Committed in:** fc5426f

**7. [Rule 1 - Bug] Phone merge test used formatting the normalizer doesn't produce**
- **Found during:** Task 06 (RED)
- **Issue:** `normalize_phone` is digits-only (RESEARCH: no country-prefix normalization) — "415-555-0132" vs "+1-415-555-0132" differ in digits
- **Fix:** Kept variant formats with identical digits: "+1-415-555-0132"
- **Files modified:** tests/test_discovery_dedup.py
- **Verification:** merge tests pass
- **Committed in:** fc5426f

**8. [Rule 1 - Bug] T09 test asserted the wrong parsed/found ratio**
- **Found during:** Task 09 (GREEN verification)
- **Issue:** Seeded found=21/parsed=15 renders "15/21" (parsed/found per spec) but the test asserted "12/15"
- **Fix:** Assertion updated to "15/21"; invariants preserved (15 == 12+3, 10+5 == 15)
- **Files modified:** tests/test_discovery_api.py
- **Verification:** dashboard test passes
- **Committed in:** 702d31e

**9. [Rule 1 - Bug] JSONB reordered rejection buckets scrambled the render line**
- **Found during:** Task 09 (GREEN verification)
- **Issue:** Postgres jsonb sorts keys — {"missing_website":4,"too_short":2} round-tripped as too_short-first
- **Fix:** Server-side sort count-desc/reason-asc before joining the bucket line
- **Files modified:** backend/api/discovery.py
- **Verification:** "missing_website 4 · too_short 2" renders as planned
- **Committed in:** 702d31e

**10. [Rule 2 - Missing Critical] DISABLED/EXCLUDED sources rendered "0/0" cells**
- **Found during:** Task 09 (GREEN verification)
- **Issue:** The view model showed "0/0" for disabled/excluded sources instead of the "—" the UI-SPEC requires
- **Fix:** `cell_display = "—"` for DISABLED/EXCLUDED statuses
- **Files modified:** backend/api/discovery.py
- **Verification:** disabled cells assert "—" in the dashboard test
- **Committed in:** 702d31e

**11. [Rule 3 - Blocking] httpx 0.28 `raise_for_status` raises on 3xx — redirect handling**
- **Found during:** Task 06 (GREEN)
- **Issue:** The compliant door raises HTTPStatusError on 3xx (by design), so `_fetch_homepage` never saw redirect responses
- **Fix:** Peel the response off the exception and re-validate each hop (loop, cap 3)
- **Files modified:** backend/services/discovery/enricher.py
- **Verification:** redirect-to-internal test asserts `calls == ["/"]` (only the first hop)
- **Committed in:** 7307139

---

**Total deviations:** 11 auto-fixed (10 Rule 1, 1 Rule 2, 1 Rule 3 — counts overlap; 9 distinct commits)
**Impact on plan:** All auto-fixes were correctness/test-infrastructure fixes within the task files. No scope creep, no new dependencies.

## Issues Encountered
- pytest truncates long assertion strings (assertion HTML was ellipsized) — debug via `open("/tmp/…", "w")` dump in the test during iteration, then removed
- `tests/test_database.py` black drift is pre-existing (unchanged since `1513257`) — logged in `deferred-items.md`, out of scope per the scope boundary

## User Setup Required
None - no external service configuration required. Live source keys (YELP_API_KEY, GOOGLE_PLACES_API_KEY) are optional and gate those sources off until provided.

## Next Phase Readiness
- Pipeline is end-to-end: trigger → outbox → worker → run (collect/normalize/dedup/enrich) → stats + lineage + leads visible on the dashboard
- Enrichment covers email/phone/form-url only — the 10-field LEAD-02 set is scored for display; deeper website auditing (playwright) is a later phase (02.1-website-audits)
- Daily discovery (`discovery-daily`, hour 0 UTC) is registered; the worker drains runs serially
- Follow-on phases can consume `discovery_run_source_stats` (LEAD-05), `business_source_records` (D-24 lineage), and the structured lead view model

---
*Phase: 02-discovery*
*Completed: 2026-08-05*
## Self-Check: PASSED
