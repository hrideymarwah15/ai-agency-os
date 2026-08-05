---
phase: 02-discovery
verified: 2026-08-05T16:30:00Z
status: human_needed
score: 7/7 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Log in as owner, open /discovery, click 'Run discovery', and watch the queued run drain through the outbox worker to completion; verify per-source cells, totals, dedup rate, and leads with lineage badges render"
    expected: "Run appears as 'In progress', then 'Complete' within ~10s (MOCK_MODE) with parsed/found cells, new/merged totals, and leads listed with source badges"
    why_human: "Requires a live browser session, cookie handling, and observing real-time worker drain — grep cannot verify rendered visual state or async runtime behavior"
  - test: "Visual review of the discovery page: runs table, per-source expander tables, rejection bucket lines, status badges, leads detail expanders, empty states"
    expected: "Tables align, badges/expanders render correctly, '—' cells for disabled/excluded sources, no raw JSON or sanitized prose visible anywhere"
    why_human: "Visual appearance and layout can only be assessed by eye"
  - test: "With a live network connection and SOURCE_HN_ENABLED=true (no key required), trigger a real run and confirm HN candidates arrive from hn.algolia.com and the api_source_exempt audit row is written"
    expected: "Live run completes with HN found/parsed counts > 0 and an audit entry action=api_source_exempt, entity=hn.algolia.com"
    why_human: "Depends on an external service (hn.algolia.com) and real network egress — cannot be verified offline"
  - test: "Trigger two runs and confirm the second run REUSES lineage for the same HN items (idempotency) — business count stays flat, run totals still increment"
    expected: "businesses table does not grow for re-seen items; per-run new_count reflects only genuinely new candidates"
    why_human: "End-to-end DB behavior across live app sessions; automated tests cover it in isolation but not through the running app"
gaps: []
deferred:
  - truth: "LEAD-02 tech stack enrichment depth (live adapters only fill contact fields; tech_stack stays null/[] for real sources)"
    addressed_in: "Phase 02.1 (Website Audits)"
    evidence: "Phase 02.1 requirement AUDT-02: 'System detects tech stack, CMS, hosting provider, and analytics presence' — roadmap line 82; plan explicitly scoped deeper website auditing (playwright) out of Phase 2"
---

# Phase 2: Discovery Verification Report

**Phase Goal:** As the agency owner, I want to trigger discovery runs that collect, deduplicate, and enrich business leads from compliant sources with per-run parse-success metrics, so that I can see qualified pipeline state in the dashboard with scraped content kept out of agent instruction context.
**Verified:** 2026-08-05T16:30:00Z
**Status:** human_needed (all 7/7 automated truths verified; 4 runtime/visual items need human testing)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Owner can trigger discovery on demand and see the queued run in the pipeline view | ✓ VERIFIED | `backend/api/discovery.py:360-395` — `POST /discovery/run` (owner-guarded via `get_current_owner`, origin-checked) creates `DiscoveryRun` + `OutboxEvent(topic="discovery.run")` + `discovery_triggered` audit in one tx, 302 to `/discovery`. Tests: `test_api_run_creates_run_outbox_audit`, `test_api_run_requires_login`, `test_api_run_rejects_cross_origin`. Live boot: POST without session → 302 `/auth/login`. Page renders queued/executed runs (`discovery.html`). |
| 2 | Runs collect candidates from 5 registered sources (HN live; Reddit excluded-live; Yelp/Google key-gated disabled; mock-only) with per-source rate limiting | ✓ VERIFIED | `registry.py:_ENTRIES` — 5 entries in UI column order; `test_registry_returns_five_sources_in_column_order`, key-gating tests. HN live (`sources/hn.py` fetches hn.algolia.com via `ctx.client`). All fetches route through `CompliantHTTPClient.fetch` → per-domain `DomainTokenBucket` (`http_client.py:41-48`) — per-source limiting since each source owns its API domain. Runner cap: `discovery_max_items_per_source` (`runner.py:96`). Tests: `test_429_source_yields_partial_run_and_exclusion_audit`, `test_max_items_per_source_cap_honored`. |
| 3 | Blocked platforms appear as Excluded/Blocked source rows with an audit event — never scraped around | ✓ VERIFIED | `sources/reddit.py` — no fetch code; audits `source_excluded` and raises `ParseError(BLOCKED)`; runner maps to `SourceRunStatus.BLOCKED` + `_audit_exclusion` (`runner.py:111-124`). `test_discovery_exclusion.py` asserts `calls == []` (zero requests), `rejected == 1`, exactly 1 audit row (actor system). Dashboard renders "Blocked" badge and "—" cells (`discovery.py:132-135`); `test_api_discovery_page_renders_metrics_and_leads_async` asserts "Blocked"/"Error" visible. |
| 4 | The same business from multiple sources appears exactly once with source lineage | ✓ VERIFIED | `dedup.py` — exact indexed lookups on `dedup_key_domain/email/phone` + difflib fuzzy pass (0.85, corroboration-required); `ingest_candidate` → NEW/MERGED/REUSED; `BusinessSourceRecord` lineage rows with `UNIQUE(source_id, source_item_id)` idempotency. Test `test_same_domain_merges_with_both_lineages`: two sources, same domain → 1 business, 2 lineage rows, dedup_rate 0.5. Dashboard lineage badges (`_lead_views` + `discovery.html:132-134`); test asserts "HN" + "Mock" badges for the two-source lead. |
| 5 | Owner sees per-run per-source parse-success metrics, totals, and dedup rate | ✓ VERIFIED | `DiscoveryRunSourceStat` (requests_made/found/parsed_ok/rejected/new_count/merged_count/rejection_buckets) persisted per run per source in the same tx (`runner.py:189-202`). Dashboard renders parsed/found cells, tfoot totals, dedup rate, rejection bucket lines, durations. Test asserts "15/21", "2/2", "—", tfoot "23/11/6", "Dedup rate 35%", "missing_website 4 · too_short 2", "45s", "In progress". |
| 6 | Adversarial injection fixtures are inert in stored fields and rendered pages | ✓ VERIFIED | `sanitize.py` — stdlib HTMLParser drops script/style/noscript, hard caps (512KB/20KB), control-char stripping, whitespace-tolerant LLM boundary-token guard; hostile input never raises. `tests/fixtures/injections.json` — 8 adversarial fixtures (directive, boundary tokens, script tag, mustache, malformed, truncated, control chars, large blob); `test_injections_fixture_inert` passes. Page renders structured view models only — test asserts `raw_payload`/`sanitized_text`/`source_item_id` absent from HTML; zero `|safe` in `discovery.html`. Collection loop is LLM-free; no agent code consumes `sanitized_text`. |
| 7 | Daily scheduled runs enqueue via outbox and execute through the worker | ✓ VERIFIED | `scheduler.py:97-122` — `_discovery_daily_job` (CronTrigger hour=0, id `discovery-daily`, max_instances=1) enqueues run + outbox event atomically; `test_discovery_daily_job_enqueues_run_and_event` + `test_build_scheduler_registers_discovery_daily_job`. `worker.py` — serial drain PENDING→IN_PROGRESS→execute_run→DONE/FAILED with last_error; started/cancelled in lifespan (`main.py:81-84`). Tests: serial order, FAILED on exception, clean cancellation. |

**Score:** 7/7 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | LEAD-02 tech-stack enrichment depth (live adapters fill contact fields only; tech_stack remains null/[] for real sources) | Phase 02.1 (Website Audits) | AUDT-02: "System detects tech stack, CMS, hosting provider, and analytics presence" (ROADMAP.md:82). Plan objective: "Website audits (02.1) and scoring (02.2) are OUT of scope". The 10-field set exists on `Business`, is counted in the n/10 enrichment display, and is filled from candidates when present (mock adapters). |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ---------| ------ | ------- |
| `backend/services/compliance/robots.py` | api_hosts exemption | ✓ VERIFIED | `api_hosts` param, bypass in `can_fetch`, once-per-host `api_source_exempt` audit; default `frozenset()` preserves deny-by-default |
| `backend/tools/http_client.py` | api_hosts in compliant client | ✓ VERIFIED | `build_compliant_client(api_hosts=...)` threads exemption; shared token bucket still throttles exempt hosts |
| `backend/database.py` | DiscoveryRun/SourceStat/BusinessSourceRecord + dedup columns | ✓ VERIFIED | Models at lines 495/514/540; Business dedup keys + indexes 157-172; enums RunStatus/SourceRunStatus |
| `backend/services/discovery/sources/hn.py` | Live HN + MockHN | ✓ VERIFIED | Algolia search→items→children; sanitize before yield; rejects <4-word comments |
| `backend/services/discovery/sanitize.py` | CMP-06 sanitizer | ✓ VERIFIED | `strip_html_to_text`, `strip_control_tokens` exported and used |
| `backend/services/discovery/dedup.py` | Canonical + fuzzy dedup | ✓ VERIFIED | `merge_into_master`, `ingest_candidate`, `dedup_rate` exported and used by runner |
| `backend/services/discovery/enricher.py` | SSRF-guarded enrichment | ✓ VERIFIED | `validate_enrichment_url` rejects private/link-local/ULA/userinfo/non-80-443; redirects re-validated, capped 3 |
| `backend/api/discovery.py` | Owner-guarded trigger + pipeline page | ✓ VERIFIED | Router mounted in main.py:98; trigger enqueue-only; view model structured-only |
| `backend/services/discovery/worker.py` | Outbox-polling executor | ✓ VERIFIED | `discovery_worker` exported, used in lifespan |
| `tests/fixtures/injections.json` | CMP-06 fixtures | ✓ VERIFIED | 8 adversarial cases incl. `<|endoftext|>` boundary tokens |

Artifact gate (`gsd-tools query verify.artifacts`): **10/10 passed**.

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | -- | ------ | ------- |
| `tools/http_client.py` | `RobotsPolicy.api_hosts` | `build_compliant_client(api_hosts=...)` | ✓ WIRED | gsd-tools verified; runtime path `runner.py:59` |
| `runner.py` | registry + `fetch_candidates` | `RunContext.client` | ✓ WIRED | gsd-tools verified |
| `sources/hn.py` | `sanitize.strip_html_to_text` | candidate text | ✓ WIRED | gsd-tools verified; also defensive re-sanitize in runner |
| `dedup.py` | `Business.dedup_key_domain` | indexed lookup | ✓ WIRED | gsd-tools verified |
| `api/discovery.py` | `OutboxEvent(topic="discovery.run")` | POST /discovery/run | ✓ WIRED | gsd-tools flagged false (pattern `discovery\\.run`); manual evidence: `api/discovery.py:379`, `worker.py:19`, `scheduler.py:118` all contain the literal string; regex `discovery\.run` matches source |
| `worker.py` | `execute_run(run_id)` | outbox poll → DONE/FAILED | ✓ WIRED | gsd-tools verified |
| `api/discovery.py` | `DiscoveryRunSourceStat` | view-model query | ✓ WIRED | gsd-tools verified |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `api/discovery.py` discovery_page | runs/stats/leads | Real `select(DiscoveryRun)`/`select(DiscoveryRunSourceStat)`/join `BusinessSourceRecord`+`DiscoveryRun` | Yes — DB queries, no hardcoded/static fallbacks | ✓ FLOWING |
| `runner.py` execute_run | per-source stats | `SourceStatCollector` from adapter calls + `ingest_candidate` counts, committed in one tx | Yes — real counters from real fetches (or Mock adapters in MOCK_MODE) | ✓ FLOWING |
| `worker.py` | run status | `execute_run` result; FAILED+last_error on exception | Yes | ✓ FLOWING |
| Dashboard `discovery.html` | cells | Pre-formatted view dicts; "—" only for absent stats/DISABLED/EXCLUDED (per UI-SPEC, asserted in tests) | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full test suite | `uv run pytest tests/ -q` | 160 passed, 3 warnings (non-blocking LangChain/Starlette deprecation warnings) | ✓ PASS |
| Lint | `uv run ruff check backend/ tests/ scripts/` | All checks passed | ✓ PASS |
| Types | `uv run mypy backend/` | Success: no issues found in 53 source files | ✓ PASS |
| Format | `uv run black --check backend/ tests/ scripts/` | All done — 75 files unchanged | ✓ PASS |
| Migration head | `uv run alembic current` | `0003 (head)` | ✓ PASS |
| Migration applied | psql table check on `ai_agency_os` | `discovery_runs`, `discovery_run_source_stats`, `business_source_records` all present | ✓ PASS |
| App boot | `uvicorn backend.main:app` + curl | `/health` → 200 `{"status":"ok"}`; `/discovery` → 302 `/auth/login`; `POST /discovery/run` → 302 `/auth/login` | ✓ PASS |

### Probe Execution

No probes declared in PLAN/SUMMARY; phase relies on pytest gates — covered by the behavioral spot-checks above. N/A.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| LEAD-01 | 02-PLAN | 3-5 compliant sources, per-source rate limiting | ✓ SATISFIED | 5 registered adapters; compliant door token bucket; registry gating tests |
| LEAD-02 | 02-PLAN | Enrich: name, industry, website, email, phone, location, employees, reviews, ratings, tech stack | ✓ SATISFIED | All 10 fields on `Business` + n/10 display; tech-stack depth deferred to 02.1 (documented) |
| LEAD-03 | 02-PLAN | Dedup across sources, merged once | ✓ SATISFIED | Canonical keys + fuzzy; cross-source merge test; lineage rows |
| LEAD-04 | 02-PLAN | Exclude blocking platforms, no scraping | ✓ SATISFIED | Reddit zero-request exclusion + audit; 429/403 block-for-run with audit |
| LEAD-05 | 02-PLAN | Manual trigger + per-run per-source metrics | ✓ SATISFIED | POST /discovery/run + DiscoveryRunSourceStat + dashboard |
| DASH-02 | 02-PLAN | Pipeline state: runs, metrics, leads | ✓ SATISFIED | SSR Jinja2 page (discovery.html), owner-guarded, nav-linked |
| CMP-06 | 02-PLAN | Sanitization, injection fixtures inert, no scraped content in instruction context | ✓ SATISFIED | Sanitizer + 8 fixtures + structured-only rendering; LLM-free collection loop |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers in any phase-02 file | — | None |
| `templates/discovery.html` | — | No `|safe` filter anywhere | — | None |
| `tests/test_database.py` black drift (deferred-items.md) | — | pre-existing formatting drift | ℹ️ resolved | Fixed by commit `b4ec521` — `black --check` now passes on all 75 files |

### Human Verification Required

1. **End-to-end trigger flow** — Test: Log in as owner, open `/discovery`, click "Run discovery", watch the queued run drain through the worker. Expected: run appears "In progress" then "Complete" (MOCK_MODE, ~5s poll), per-source cells, totals, dedup rate, leads with lineage badges appear. Why human: needs live browser session + observing real-time async worker behavior.
2. **Visual appearance** — Test: Review runs table, per-source expanders, rejection bucket lines, status badges, leads detail expanders, empty states, "—" cells. Why human: layout/visuals only assessable by eye.
3. **Live HN collection** — Test: With network egress and SOURCE_HN_ENABLED=true (no key required), trigger a real run. Expected: HN found/parsed > 0 from hn.algolia.com and `api_source_exempt` audit row present. Why human: external service dependency.
4. **Cross-run idempotency in the running app** — Test: Trigger two runs; confirm businesses do not duplicate for re-seen items. Why human: end-to-end DB behavior through the live app (unit-tested in isolation).

### Gaps Summary

No blocking gaps found. All 7 must-have truths verified against code, tests, migration, and a live boot. All 7 requirements (LEAD-01..05, DASH-02, CMP-06) satisfied with test evidence. Gates: pytest 160/160, ruff clean, mypy clean (53 files), black clean (75 files), alembic head 0003 applied with all three tables present in the live database, app boots with `/health` 200 and unauthenticated `/discovery` correctly redirected.

Notes:
- `gsd-tools query verify.key-links` reported one false negative (`discovery\.run` topic pattern) — manually confirmed present at `api/discovery.py:379`, `worker.py:19`, `scheduler.py:118`.
- One intentional deferral (tech-stack depth → Phase 02.1 AUDT-02) is documented, scoped, and not a failure of this phase's goal.
- Status is `human_needed` (not `passed`) because 4 runtime/visual behaviors (live session flow, page appearance, live HN egress, app-level idempotency) can only be confirmed by a human.

---

_Verified: 2026-08-05T16:30:00Z_
_Verifier: the agent (gsd-verifier)_
