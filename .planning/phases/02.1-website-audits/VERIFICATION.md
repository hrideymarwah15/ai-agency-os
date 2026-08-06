---
phase: 02.1-website-audits
verified: 2026-08-07T14:23:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 02.1: Website Audits Verification Report

**Phase Goal:** As the agency owner, I want to audit each lead's website for performance, accessibility, SEO, and mobile scores with tech stack and conversion-flow insights, so that I can assess lead quality from a timestamped audit history.

**Verified:** 2026-08-07T14:23:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                              | Status       | Evidence                                                                                           |
| --- | -------------------------------------------------------------------------------------------------- | ------------ | -------------------------------------------------------------------------------------------------- |
| 1   | Owner can trigger a website audit per lead and see RUNNING→COMPLETED/FAILED status in the audit list | ✓ VERIFIED   | `backend/api/website_audits.py:422-460` POST `/lead/{id}/run` creates RUNNING row + outbox event; `website_audits_list.html:34-48` renders status badge |
| 2   | Audit produces 4 dimension scores (performance, accessibility, SEO, mobile) 0-100 from deterministic rules | ✓ VERIFIED   | `backend/services/audits/scoring.py:21-182` four `score_*` functions using `max(0, 100-deductions)`; `runner.py:296-299` assigns to audit row |
| 3   | Core Web Vitals (LCP, CLS, INP, TTFB) stored with methodology labels (MEASURED/ESTIMATED/NOT_ASSESSED) | ✓ VERIFIED   | `scoring.py:190-221` `build_cwv_report()` with `methodology.measured_with` + `inp_estimation`; `renderer.py:130-138` captures vitals; `website_audit_detail.html:59-72` renders methodology badges |
| 4   | Tech stack, CMS, hosting provider, analytics tools detected from deterministic signature matching | ✓ VERIFIED   | `signatures.py:31-119` `_SIGNATURES` table with 87 patterns; `match_signatures()` first-match-wins for CMS/hosting, set-union for stack/analytics; `runner.py:258,301-304` stores results |
| 5   | Broken links found (capped sample) and stored with HTTP status codes                               | ✓ VERIFIED   | `runner.py:114-135` `_link_pass()` internal capped at `audit_broken_link_sample` (20), external at `audit_external_link_cap` (5); `_probe_status()` returns status_code |
| 6   | Conversion-flow gaps detected (missing contact form, CTA, phone, etc.)                             | ✓ VERIFIED   | `static_analyzer.py:319-335` `find_conversion_gaps()` returns 5 gap kinds; `runner.py:292,306` stores; `website_audit_detail.html:123-134` renders |
| 7   | Audit history per lead — newest-first — re-audit creates new row, never overwrites                | ✓ VERIFIED   | `website_audits.py:387-398` lead page orders by `started_at.desc()`; `run_website_audit:436-440` inserts NEW `WebsiteAudit` row; `D-39` in CONTEXT.md |
| 8   | All fetching through compliant door (robots + token bucket); Playwright gated on pre-check        | ✓ VERIFIED   | `http_client.py:42-64` `fetch()`/`fetch_stream()` enforce robots + bucket; `runner.py:240` uses `client.fetch()`; `renderer.py:81-91` `browser_available()` probe before render |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact                                    | Expected                                        | Status | Details                                                              |
| ------------------------------------------- | ----------------------------------------------- | ------ | -------------------------------------------------------------------- |
| `backend/services/audits/runner.py`         | Audit execution orchestrator                    | ✓ VERIFIED | 364 lines; `execute_audit()` orchestrates static→rendered→links→ONE commit |
| `backend/services/audits/worker.py`         | Outbox worker for audit.run topic               | ✓ VERIFIED | 71 lines; `audit_worker()` polls serially, marks DONE/FAILED       |
| `backend/database.py`                       | WebsiteAudit model + AuditStatus enum + JSONB   | ✓ VERIFIED | Lines 573-613: `WebsiteAudit` with all JSONB columns, status enum, index |
| `backend/services/audits/signatures.py`     | Deterministic detection table                   | ✓ VERIFIED | 192 lines; 87 compiled regex patterns across 5 categories          |
| `backend/services/audits/scoring.py`        | Rule-based 0-100 scoring per dimension          | ✓ VERIFIED | 222 lines; 4 scoring passes + `build_cwv_report()` with methodology |
| `backend/services/audits/renderer.py`       | Playwright-gated rendered analysis              | ✓ VERIFIED | 153 lines; `browser_available()` CI gate; `render_audit()` CWV observer |
| `backend/services/audits/static_analyzer.py`| Static HTML analysis + conversion gaps          | ✓ VERIFIED | 336 lines; `analyze_html()` + `find_conversion_gaps()`             |
| `backend/api/website_audits.py`             | API routes + structured view models             | ✓ VERIFIED | 518 lines; 4 routes (index, lead, trigger, detail); T-03-01 view models |
| `backend/tools/http_client.py`              | Compliant HTTP door with `fetch_stream`         | ✓ VERIFIED | 95 lines; `fetch_stream()` for TTFB + header-only probes           |
| `backend/alembic/versions/0004_*.py`        | Website audit schema migration                  | ✓ VERIFIED | Creates `website_audits` table with all JSONB columns + index      |
| `backend/templates/website_audits_list.html`| Audit list page                                 | ✓ VERIFIED | 57 lines; renders leads with latest audit, scores, status, actions |
| `backend/templates/website_audits_lead.html`| Per-lead audit history + trigger                | ✓ VERIFIED | 48 lines; newest-first history, dynamic "Run audit"/"Re-audit"     |
| `backend/templates/website_audit_detail.html`| Full audit detail page                         | ✓ VERIFIED | 167 lines; scores, CWV table, tech stack, broken links, gaps, history |

### Key Link Verification

| From                          | To                              | Via                                    | Status | Details                                                            |
| ----------------------------- | ------------------------------- | -------------------------------------- | ------ | ------------------------------------------------------------------ |
| `website_audits.py:443-448`   | `OutboxEvent(topic="audit.run")`| Same transaction as RUNNING row        | ✓ WIRED | `session.add(audit)` + `session.add(OutboxEvent)` + `commit()`    |
| `main.py:74-75`               | `audit_worker()`                | `asyncio.create_task()` in lifespan    | ✓ WIRED | Worker task started with app, cancelled on shutdown               |
| `worker.py:60`                | `execute_audit()`               | `await execute_audit(..., renderer=default_renderer)` | ✓ WIRED | Production renderer seam injected                                |
| `runner.py:240`               | `CompliantHTTPClient.fetch()`   | `client = build_client(); client.fetch()` | ✓ WIRED | All fetching through compliant door (D-32)                       |
| `renderer.py:81-91`           | Playwright chromium             | `browser_available()` probe            | ✓ WIRED | CI skip gate — degrades to static when browser unavailable        |
| `runner.py:274-280`           | `renderer()` seam               | `if renderer: rendered = await renderer(url)` | ✓ WIRED | Gated rendered pass; `None` = static-only mode                   |
| `scoring.py:190-221`          | CWV methodology labels          | `build_cwv_report(ttfb_ms, rendered)`  | ✓ WIRED | Static: `measured_with="static"`, `inp_estimation="not_assessed"` |

### Data-Flow Trace (Level 4)

| Artifact                          | Data Variable          | Source                                  | Produces Real Data | Status |
| --------------------------------- | ---------------------- | --------------------------------------- | ------------------ | ------ |
| `runner.py:296-299`               | `performance_score` etc.| `score_performance(signals)`            | Yes — measured signals from HTML + optional rendered | ✓ FLOWING |
| `runner.py:300`                   | `cwv`                  | `build_cwv_report(ttfb_ms, rendered)`   | Yes — TTFB from door; LCP/CLS/INP from Playwright | ✓ FLOWING |
| `runner.py:301-304`               | `tech_stack`, `cms`, etc.| `match_signatures(html, headers, cookies)` | Yes — 87 regex patterns on real response | ✓ FLOWING |
| `runner.py:305`                   | `broken_links`         | `_link_pass()` via door                 | Yes — capped probes with real status codes | ✓ FLOWING |
| `runner.py:306`                   | `gaps`                 | `find_conversion_gaps(stats)`           | Yes — parsed from real HTML | ✓ FLOWING |
| `website_audits.py:265-297`       | `_to_audit_view()`     | ORM row → structured dict               | Yes — all fields pre-formatted for templates | ✓ FLOWING |
| `website_audit_detail.html`       | `audit.scores` etc.    | `_to_audit_view()` output               | Yes — Jinja2 renders structured data | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior                                  | Command                                    | Result       | Status |
| ----------------------------------------- | ------------------------------------------ | ------------ | ------ |
| Full test suite passes                    | `uv run pytest tests/ -q`                  | 240 passed   | ✓ PASS |
| Audit-specific tests pass                 | `uv run pytest tests/test_audit_*.py tests/test_website_audits_api.py -q` | 78 passed    | ✓ PASS |
| Ruff lint clean                           | `uv run ruff check backend/ tests/`        | clean        | ✓ PASS |
| Black format check                        | `uv run black --check backend/ tests/`     | 91 files ok  | ✓ PASS |
| Mypy type check                           | `uv run mypy backend/`                     | no issues    | ✓ PASS |
| Alembic migration current                 | `uv run alembic check`                     | no new ops   | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description                                              | Status   | Evidence                                              |
| ----------- | ----------- | -------------------------------------------------------- | -------- | ----------------------------------------------------- |
| AUDT-01     | 02.1-PLAN.md | Performance, accessibility, SEO, mobile scores (INP-based CWV, not FID) | ✓ SATISFIED | `scoring.py` 4 passes; `renderer.py` INP via event-timing + longtask proxy; FID never used |
| AUDT-02     | 02.1-PLAN.md | Tech stack, CMS, hosting, analytics detected from signature matching | ✓ SATISFIED | `signatures.py` 87 patterns; first-match-wins CMS/hosting; set-union stack/analytics |
| AUDT-03     | 02.1-PLAN.md | Broken links, missing forms, conversion-flow gaps        | ✓ SATISFIED | `runner.py:_link_pass()` capped; `static_analyzer.py:find_conversion_gaps()` 5 gap kinds |
| AUDT-04     | 02.1-PLAN.md | Audit results per lead with timestamped history          | ✓ SATISFIED | `WebsiteAudit` model + `started_at`; lead page newest-first; re-audit = new row |

### Anti-Patterns Found

| File                                    | Line | Pattern                 | Severity | Impact |
| --------------------------------------- | ---- | ----------------------- | -------- | ------ |
| None found in phase-modified files      | —    | —                       | —        | All code follows D-36 (deterministic rules), CMP-06 (sanitization), T-03-01 (structured view models) |

No `TBD`/`FIXME`/`XXX` markers in any phase-modified file. No empty implementations, no hardcoded empty data flowing to UI, no console.log-only handlers.

### Human Verification Required

None — all must-haves are programmatically verifiable and have been verified. The phase is complete and ready to proceed.

### Gaps Summary

No gaps found. All 8 observable truths are verified with code evidence. All 14 required artifacts exist, are substantive, and are properly wired. All 7 key links are verified. All 4 requirements (AUDT-01..04) are satisfied. The full test suite (240 tests) passes with all lint gates clean.

---

_Verified: 2026-08-07T14:23:00Z_
_Verifier: the agent (gsd-verifier)_