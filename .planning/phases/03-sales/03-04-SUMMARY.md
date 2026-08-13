---
phase: 03-sales
plan: 04
subsystem: proposal-generation
tags: [proposals, jinja2, pricing, pdf, docx, outbox, owner-api, signed-links]
requires:
  - phase: 03-sales-01
    provides: deterministic PricingEngine and negotiation limits
  - phase: 03-sales-03
    provides: proposal.generate outbox event handoff after booked meetings
provides:
  - ten-section structured Proposal persistence and Jinja template engine
  - deterministic proposal generation from lead, audit, opportunities, meeting notes, and pricing
  - optional PDF/DOCX rendering with printable HTML and graceful dependency errors
  - async proposal.generate worker and owner lifecycle API
  - versioned owner edits, approval audit, durable delivery handoff, and signed client access
affects: [03-sales-05, 03-sales-06, legal, dashboard]
tech-stack:
  added: []
  patterns: [Jinja autoescape, additive Alembic migration, bounded PDF rendering, signed expiring client links, durable outbox handoff]
key-files:
  created:
    - backend/alembic/versions/0009_proposal_generator.py
    - backend/services/proposal/__init__.py
    - backend/services/proposal/templates.py
    - backend/services/proposal/generator.py
    - backend/services/proposal/pdf.py
    - backend/services/proposal/worker.py
    - backend/api/proposals.py
    - backend/templates/proposals/*.j2
    - backend/templates/proposal.html
    - tests/test_proposal_generator.py
    - tests/test_proposal_templates.py
    - tests/test_proposal_pdf.py
    - tests/test_proposal_api.py
  modified:
    - backend/database.py
    - backend/main.py
    - backend/static/app.css
decisions:
  - "Use Alembic revision 0009 because 0006 is already pricing_engine and 0008 is the current migration head."
  - "Proposal send creates proposal.deliver durable outbox work and does not claim an email was sent without a configured delivery consumer."
  - "Client proposal access uses an itsdangerous signed token plus a database hash and expiry, with noindex headers and view audit logging."
  - "Proposal delivery uses DELIVERY_QUEUED until SendGrid accepts the message; only then are Proposal.SENT and Business.NEGOTIATING committed."
metrics:
  duration: "about 2h"
  completed: 2026-08-13
  tasks: 3
  files: 35
---

# Phase 03 Plan 04: Proposal Generator Summary

**Ten-section, pricing-backed proposal generation with owner review, versioned edits, signed client access, and durable delivery handoff.**

## Accomplishments

- Extended `Proposal` with structured sections, pricing snapshot, HTML/component output, version history, lifecycle timestamps, and client token metadata.
- Added migration `0009_proposal_generator.py` chained from the live `0008` head.
- Added Jinja component blocks for executive summary, audit, opportunities, scope, timeline, pricing, FAQs, testimonials, terms, and next steps, plus website, automation, chatbot, and custom AI variants.
- `ProposalGenerator` loads the lead and latest audit, consumes persisted opportunities, calls `PricingEngine.compute`, renders the complete HTML and ten component fragments, and audits generation with the proposal correlation ID.
- `PDFRenderer` supports WeasyPrint first, Playwright fallback, printable HTML, and optional `python-docx` output. Rendering is bounded by a semaphore and timeout; missing optional dependencies return an explicit runtime error.
- Added the serial `proposal.generate` outbox worker, owner-protected proposal routes, signed expiring client view, owner builder shell, pricing/version panels, approval flow, and durable `proposal.deliver` handoff.
- Owner section edits are validated against executable HTML markers, versioned, snapshot prior content, and audit logged. Approval enqueues `contract.generate`; delivery changes the business to `NEGOTIATING` only after approval and client email validation.
- Verifier remediation replaced marker checks with a conservative HTML parser/allowlist, added `DELIVERY_QUEUED`, implemented SendGrid delivery consumption with retries/stale recovery/idempotency, made migration startup fail closed, and upgraded the builder with contenteditable sections, bounded pricing controls, and version comparison.

## Task Commits

1. `76c8bb4` — structured proposal persistence, migration, generator contract, and templates
2. `03a58c3` — PDF/HTML/DOCX renderer and proposal outbox worker
3. `2e30dc5` — owner API, builder UI, focused proposal tests, and router registration
4. `7bcea5f` — proposal worker startup/shutdown wiring in lifespan
5. `e806c10` — executable HTML validation for owner edits
6. `ff22e03` — verifier remediation for enum migration, sanitization, durable delivery, rendering, builder, and regression coverage

## Verification

- `pytest tests/test_proposal_generator.py tests/test_proposal_templates.py tests/test_proposal_pdf.py tests/test_proposal_api.py -q` — **15 passed**.
- `pytest tests/test_proposal_generator.py tests/test_proposal_templates.py tests/test_proposal_pdf.py tests/test_proposal_api.py tests/test_pricing_engine.py tests/test_pricing_rules.py tests/test_meeting_scheduler.py tests/test_outreach_integration.py -q` — **30 passed**, 7 existing/dependency warnings.
- `python3 -m compileall -q` over proposal source, API, database, lifespan, migration, and proposal tests — passed.
- `alembic heads` — `0009 (head)`; `0008 -> 0009` migration chain confirmed.
- OpenAPI route smoke check confirmed proposal list/generate/PDF and signed client-view paths.
- `git diff --check` over all plan files — passed.
- Verifier remediation suite (proposal generator/templates/PDF/API/migration/worker plus pricing, meeting, and outreach integration) — **49 passed**, 7 existing environment/deprecation warnings.
- Committed `backend/main.py` compiled independently after repairing the prior malformed gather list; migration exceptions and 30-second timeouts now abort startup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking migration issue] Used the next valid migration revision**
- **Found during:** Task 1
- **Issue:** The plan's `0006_proposal_generator.py` name was stale; `0006` is already pricing engine and `0008` is the current head.
- **Fix:** Created `0009_proposal_generator.py` with `down_revision = "0008"` and additive proposal columns/indexes.
- **Files modified:** `backend/alembic/versions/0009_proposal_generator.py`
- **Commit:** `76c8bb4`

**2. [Rule 2 - Security] Added executable HTML validation for owner edits**
- **Found during:** Task 3 threat-surface review
- **Issue:** Autoescaping protects template context, but owner-provided section HTML is intentionally inserted as rendered markup and needed an explicit executable-content guard.
- **Fix:** Reject script, javascript URLs, embedded executable tags, and common event-handler attributes before persisting edits; added focused coverage.
- **Files modified:** `backend/api/proposals.py`, `tests/test_proposal_api.py`
- **Commit:** `e806c10`

**3. [Rule 1 - Lifecycle bug] Deferred SENT/NEGOTIATING until provider success**
- **Found during:** Independent verifier review
- **Issue:** The API marked delivery complete before any provider attempt, and worker claims had no stale recovery or retry scheduling.
- **Fix:** Added `DELIVERY_QUEUED`, a SendGrid-backed `proposal.deliver` consumer, three-attempt retry scheduling, stale claim recovery, idempotent SENT handling, and correlation audit after successful provider acceptance.
- **Files modified:** `backend/database.py`, `backend/alembic/versions/0009_proposal_generator.py`, `backend/api/proposals.py`, `backend/services/proposal/worker.py`, `backend/services/outreach/clients.py`
- **Commit:** `ff22e03`

**4. [Rule 1 - Migration bug] Evolved PostgreSQL enum safely**
- **Found during:** Independent verifier review
- **Issue:** ORM enum labels were absent from the existing `proposalstatus` type.
- **Fix:** Upgrade adds `APPROVED` and `DELIVERY_QUEUED` before new columns; downgrade normalizes rows and realistically rebuilds the PostgreSQL enum without those labels.
- **Files modified:** `backend/alembic/versions/0009_proposal_generator.py`
- **Commit:** `ff22e03`

### Intentional Adjustments

- Existing `backend/main.py` had unrelated dirty lifespan/router changes from prerequisite work. Only proposal router and worker additions were staged; all other changes remain uncommitted.
- The repository does not currently install WeasyPrint or Playwright. No package was installed. PDF/DOCX code fails clearly with HTTP 503/runtime errors when optional dependencies are absent, while HTML remains available; fallback and dual-failure paths are covered by injected tests.
- SendGrid delivery is now implemented, but production delivery still requires a valid `SENDGRID_API_KEY` and verified sender. Without credentials, the durable event retries and remains `DELIVERY_QUEUED`, then becomes `FAILED` after three attempts.

## Known Stubs

- `backend/templates/proposals/testimonials.j2`: v1 testimonial data is intentionally empty until approved testimonials/content are supplied; the section still renders and is persisted.
- `backend/services/proposal/pdf.py`: Playwright fallback requires the already-declared browser package and installed Chromium; this environment lacks both optional renderer paths, so live PDF bytes were not produced locally.

## Deferred Issues

- Apply `alembic upgrade head` against a configured PostgreSQL database during deployment; the local environment used migration graph/compile verification because no database credentials/server were available.
- Implement the downstream contract generation consumer in the subsequent legal plan.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: signed-client-access | `backend/api/proposals.py` | New external client proposal view is protected by a signed, hashed, expiring token and audited on view. |
| threat_flag: rendered-html | `backend/api/proposals.py` | Owner edits are validated before being inserted into rendered section HTML; noindex/no-store headers are used for proposal views. |

## Self-Check: PASSED

- Created files exist, including migration, proposal service/API/templates, builder, and four focused test modules.
- Commits `76c8bb4`, `03a58c3`, `2e30dc5`, `7bcea5f`, `e806c10`, and `ff22e03` exist in git history.
- Unrelated dirty worktree changes were preserved and not staged by this plan.

---
*Phase: 03-sales*
*Completed: 2026-08-13*
