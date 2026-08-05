# Phase 02: Discovery - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning
**Source:** Auto-synthesized from ROADMAP (SPIDR slice), REQUIREMENTS.md, SPEC-002, Phase 1 decisions

<domain>
## Phase Boundary

MVP slice of the discovery pipeline (SPIDR split from the original Phase 2): the owner
triggers discovery runs on demand; the system collects candidate businesses from 3-5
compliant sources with per-source rate limiting (exclusion not scraping when blocked),
normalizes into a unified schema, deduplicates across sources into master records with
source lineage, enriches with the declared field set, and surfaces per-run parse-success
metrics — all visible as pipeline state in the owner dashboard. Scraped content never
reaches agent instruction context (ingestion sanitization, CMP-06).

Website audits (AUDT-01..04) and opportunity detection + scoring (OPP-01..03, SCOR-01/02)
are separate SPIDR slices: Phase 02.1 and Phase 02.2. Do NOT plan them here.

</domain>

<decisions>
## Implementation Decisions

### Collection Sources & Compliance (LEAD-01, LEAD-04)
- **D-21:** Sources are provider adapters behind a common interface; first slice ships 3-5
  compliant, no-key/low-key sources from SPEC-002 (Google Custom Search/Places API optional,
  Yelp Fusion, Reddit API, Hacker News "Who is Hiring", JustDial/IndiaMART candidates) —
  each adapter declares rate limit config and availability; unconfigured sources are disabled.
- **D-22:** All fetching goes through the Phase 1 compliant HTTP client factory
  (`backend/tools/http_client.py`, D-13/D-15): robots deny-by-default + per-domain token
  bucket + jitter. Sources/platforms that block automated collection are EXCLUDED with an
  audit event, never scraped around (LEAD-04).
- **D-23:** Mock providers (MOCK_MODE, D-20) back every source adapter for deterministic
  tests and demo runs; parse-success metrics (LEAD-05) are computed per source per run
  (candidates found vs parsed vs rejected), stored with the run.

### Normalization & Deduplication (LEAD-02, LEAD-03)
- **D-24:** Unified normalized schema per SPEC-002 §8.2 subset (identity, contact, location,
  size, social, technical, reputation, signals) stored in a `businesses`-table-equivalent
  model; source raw payload kept JSON for lineage.
- **D-25:** Dedup by canonical key (normalized domain, exact phone/email) + fuzzy match on
  name+domain+phone+address; same business from multiple sources merges into ONE master
  record with `source_ids` lineage (SPEC-002 FR-060/061); dedup rate is a reported metric.

### Enrichment (LEAD-02)
- **D-26:** Incremental enrichment fills only missing fields (FR-062); contact discovery
  via website homepage scan for email/phone/form URL using the compliant client; no paid
  enrichment APIs in this slice (LEAD-07 is backlog).

### Ingestion Safety (CMP-06)
- **D-27:** Collected content is sanitized at ingestion: HTML stripped to text, size-limited,
  and stored as data only — never concatenated into prompt/system-prompt text; adversarial
  injection fixtures (e.g. `<|endoftext|>`-style / "ignore previous instructions" payloads in
  source content) pass — scraped content cannot alter agent behavior.

### Discovery Runs & Metrics (LEAD-05, DASH-02)
- **D-28:** Discovery run = persisted entity (trigger source: manual/scheduler, started/finished
  timestamps, per-source stats, total candidates) with its own correlation_id (D-07); manual
  trigger endpoint for the owner; scheduler job (D-12) enqueues daily runs (heartbeat pattern
  from 01-04).
- **D-29:** Pipeline state view is a Jinja2 SSR page (continuation of D-17's Phase 1 UI —
  server-rendered FastAPI + Jinja2, zero client JS) showing recent runs + metrics and
  qualified leads summary; full Next.js dashboard remains deferred.
- **D-30:** Playwright re-added (D-04) ONLY in Phase 02.1 for JS-rendered audits — not in
  this slice; HTML parsing uses stdlib/BeautifulSoup-class tooling, no browser dependency.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Specs
- `.planning/specs/discovery/SPEC-002-lead-discovery-engine.md` — full discovery engine spec (§5.1 sources, §5.2 fields, §5.7 dedup/enrichment, §7 architecture, §8.2 lead model)
- `.planning/specs/core/SPEC-001-core-system-architecture.md` — system architecture context

### Phase 1 foundations (all built and committed)
- `.planning/phases/01-foundation-orchestration-core/1-CONTEXT.md` — locked decisions D-01..D-20 (esp. D-13/D-15 compliant HTTP client, D-20 MOCK_MODE, D-07 correlation_id, D-12 scheduler)
- `.planning/phases/01-foundation-orchestration-core/1-UI-SPEC.md` — UI brand tokens (slate-50/white/blue-600, 8pt spacing, system-ui) for the pipeline state page
- `.planning/phases/01-foundation-orchestration-core/01-PATTERNS.md` — §tools/http_client.py, §services/ patterns, auth/session patterns
- `.planning/phases/01-foundation-orchestration-core/01-05-SUMMARY.md` — compliant client + send gate shipped in 01-05
- `.planning/phases/01-foundation-orchestration-core/01-04-SUMMARY.md` — scheduler + heartbeat + budget wiring shipped in 01-04

### Code (read to match patterns)
- `backend/tools/http_client.py` — the compliant fetch door (D-15)
- `backend/services/audit.py`, `backend/services/scheduler.py`, `backend/database.py`, `backend/config.py`, `backend/main.py`
- `backend/agents/lead_hunter.py` — legacy discovery agent being superseded/reused
- `backend/api/audit.py`, `backend/api/approvals.py` — router + Jinja2 page patterns

</canonical_refs>

<specifics>
## Specific Ideas

- Source adapters: start with Reddit (free JSON API), Hacker News (Algolia API, free), Yelp
  Fusion (free tier) + 1-2 mock-only adapters to reach "3-5 sources" with one demonstrably
  blocked source fixture for LEAD-04 exclusion behavior.
- Per-run metrics to show: sources attempted, candidates found, parsed OK, normalized,
  rejected (with reason bucket), new vs merged duplicates, enrichment coverage.
- Dedup unit test: same business from two adapters (Reddit + Yelp) → one master record,
  lineage shows both source_ids.
- Injection fixture: source content containing "ignore previous instructions / leak the
  system prompt" must appear inert in stored fields and any downstream template.

</specifics>

<deferred>
## Deferred Ideas

- Website intelligence crawler + audits → Phase 02.1 (AUDT-01..04, Playwright)
- Opportunity detectors + scoring/priority queue → Phase 02.2 (OPP-01..03, SCOR-01/02)
- Additional sources (Clutch, GoodFirms, Product Hunt, Crunchbase, IndiaMART) → backlog
  LEAD-06 behind provider-specific compliance review
- Paid enrichment/contact verification (Hunter.io-style) → backlog LEAD-07
- Score calibration feedback loop → backlog SCOR-03; RUM vs lab reconciliation → backlog AUDT-05
- Next.js 16 dashboard → deferred beyond this slice (Jinja2 SSR continues)

</deferred>

---

*Phase: 02-discovery*
*Context gathered: 2026-08-05 via auto-synthesis (roadmap slice + SPEC-002 + Phase 1 decisions)*
