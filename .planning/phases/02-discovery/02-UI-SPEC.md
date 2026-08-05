---
phase: 2
slug: discovery
status: approved
reviewed_at: 2026-08-05
shadcn_initialized: false
preset: none
created: 2026-08-05
---

# Phase 02 — UI Design Contract (Discovery)

> Visual and interaction contract for the Phase 2 pipeline-state page (DASH-02): a Jinja2 SSR continuation of the Phase 1 owner UI (locked D-29 — zero client JS, FastAPI + Jinja2, shared `app.css`; the Next.js dashboard remains deferred beyond this slice). **Design-system rule: reuse Phase 1 tokens and component primitives verbatim (1-UI-SPEC.md, approved c7f47d5) — no new design decisions, no token overrides.** The only additions are (a) one new status-badge color pair for the RUNNING run state and (b) two mechanical CSS primitives (`.table-scroll`, `.num`) plus badge variants — all documented below as the complete delta.

---

## Design System

| Property | Value (unchanged from Phase 1 — 1-UI-SPEC.md §Design System) |
|----------|-------|
| Tool | none — hand-rolled CSS in `backend/static/app.css`, plain CSS custom properties; shadcn init not applicable (D-29: Jinja2 SSR continuation; Next.js + shadcn deferred beyond this slice) |
| Preset | not applicable |
| Component library | none — existing CSS class primitives named to mirror shadcn components |
| Icon library | none — text labels + status badges only; zero external assets |
| Font | system-ui stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`; mono exception: `SF Mono, Menlo, Consolas, monospace` at 13px (run ID only) |
| CSS delivery | one static stylesheet, CSS custom properties (`:root`), no preprocessor, no bundler |

---

## Pages in Scope

| Route | Template | Requirement | Purpose |
|-------|----------|-------------|---------|
| `GET /discovery` | `discovery.html` (new) | DASH-02, LEAD-05 | Pipeline-state page: recent discovery runs with per-run per-source parse-success metrics, run totals, and qualified-leads summary with source lineage |
| `POST /discovery/run` | none — 302 → `/discovery` | LEAD-05, D-28 | Manual trigger: creates `DiscoveryRun` (trigger_source=MANUAL) + `OutboxEvent(topic="discovery.run")`, sets success flash, redirects (owner-guarded + `_check_origin`, per `backend/api/approvals.py` pattern) |
| `base.html` (modify) | — | D-29 | Add "Discovery" nav link with the existing `active_page` highlight pattern |
| `app.css` (modify) | — | D-29 | Add §Phase 2 delta primitives only (see Component Specs) — never restyle Phase 1 tokens |

No new routes beyond these. `/approvals` remains the post-login landing page (Phase 1 contract, unchanged). Any 401 on `/discovery` → redirect to `/auth/login` with flash "Your session has expired. Please log in again." (Phase 1 rule, applies unchanged).

**Locked route note:** upstream artifacts decide the route — CONTEXT D-29 + RESEARCH §Recommended Project Structure specify `backend/api/discovery.py` with `GET /discovery` + `POST /discovery/run` and `templates/discovery.html`. Not `/dashboard`, not `/leads`.

---

## Layout Contract

Same shell as Phase 1 (top nav + constrained main, `max-width: 960px`, `padding: 32px 16px 48px`). The discovery page is single-column, in this fixed order:

1. **Page header** — Display title "Discovery" + one-line muted description: "Pipeline state for lead discovery: run history, per-source parse metrics, and qualified leads."
2. **Action row** — the "Run discovery" primary button (POST form) with a muted 14px note beside it: "Queued runs execute in order." (worker serialization, RESEARCH Pattern 2 — the UI never disables the button; double-submits enqueue serially).
3. **Configuration banner** (only when zero sources enabled) — see Secondary States.
4. **Runs section** — Heading "Recent runs" (20px) + runs table with `tfoot` totals + "Showing the most recent 10 runs." muted note below.
5. **Leads section** — Heading "Qualified leads" (20px) + leads table + "Showing the most recent 20 leads. The full lead list arrives with the Next.js dashboard." muted note below. Section hidden entirely when no runs exist.

Sections separated by 32px (`--space-xl`); section headings carry 16px bottom gap to their tables. The 960px shell is kept — the wide runs table scrolls horizontally inside `.table-scroll` rather than widening the page (desktop tool, consistent with Phase 1).

Nav order (base.html): **Discovery · Approval Queue · Audit Log** — Discovery leads as the primary pipeline-state view (DASH-02); the pending-count badge behavior is unchanged. Active page sets `active_page == 'discovery'`.

---

## Spacing Scale

**Verbatim Phase 1 contract (no exceptions):** xs 4px / sm 8px / md 16px / lg 24px / xl 32px / 2xl 48px / 3xl 64px — all multiples of 4, mapping 1:1 to Tailwind v4. Buttons/inputs remain 36px tall. No 44px touch targets — desktop-only internal tool (Phase 1 exception, unchanged).

---

## Typography

**Verbatim Phase 1 contract:**

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Display (page title) | 24px | 600 | 1.2 |
| Heading (section titles) | 20px | 600 | 1.2 |
| Body / table cells | 16px | 400 | 1.5 |
| Label/caption (14px: badges, th, meta, muted notes, detail-list labels) | 14px | 400 | 1.4 |

Exactly 2 weights: 400 + 600. Code-face exception (not part of the scale): run ID renders as a plain 13px `font-family: var(--font-mono)` span (no `.mono-payload` block styling — new `.run-id` class).

---

## Color

**Verbatim Phase 1 contract:** dominant `#F8FAFC` (slate-50) · secondary `#FFFFFF` · border `#E2E8F0` (slate-200) · text `#0F172A` (slate-900) · muted `#475569` (slate-600) · accent `#2563EB` (blue-600) · destructive `#DC2626` (red-600). Flash pairs unchanged (success green / error red).

**Accent remains reserved for exactly:** primary action buttons ("Run discovery"), the active nav link, inline text links, the focus-visible ring, and expander `<summary>` affordances (existing queue-details pattern). Never for: badges, borders, backgrounds, secondary text, table cells, or hover tints.

**Status badge table (all text-on-tint pairs ≥ 4.5:1; text label always present — color is never the sole indicator):**

| Domain | Status | Label | Text / BG |
|--------|--------|-------|-----------|
| Run | RUNNING | "In progress" | `#1D4ED8` (blue-700) on `#DBEAFE` (blue-100) — **the only new pair** (see note) |
| Run | COMPLETED | "Complete" | `#15803D` on `#DCFCE7` (reuse approved) |
| Run | PARTIAL | "Partial" | `#B45309` on `#FEF3C7` (reuse pending) |
| Run | FAILED | "Failed" | `#B91C1C` on `#FEE2E2` (reuse rejected) |
| Source | OK | "OK" | `#15803D` on `#DCFCE7` (reuse approved) |
| Source | EMPTY | "Empty" | `#B45309` on `#FEF3C7` (reuse pending) |
| Source | BLOCKED | "Blocked" | `#B91C1C` on `#FEE2E2` (reuse rejected) |
| Source | ERROR | "Error" | `#7C3AED` (violet-600) on `#EDE9FE` (reuse escalated) |
| Source | EXCLUDED | "Excluded" | `#475569` (slate-600) on `#F1F5F9` (reuse expired) |
| Source | DISABLED | "Disabled" | `#475569` (slate-600) on `#F1F5F9` (reuse expired) |
| Trigger | — | "Manual" / "Scheduled" | `.badge--action` (bordered neutral — existing) |
| Lineage | — | source short name ("HN", "Reddit", …) | `.badge--source` (bordered neutral — new, same look as `.badge--action`) |

**Note on the single new pair:** Phase 1's five badge hues cover queue/audit statuses but not an "in progress" state; blue-700/blue-100 is a stock Tailwind v4 token (contrast ≈ 5.5:1 on the tint — passes AA), mirrors the existing badge-table construction, and does NOT touch the accent hex (blue-600 `#2563EB` stays badge-free). This is the only new `:root` variable pair: `--blue-text: #1D4ED8; --blue-bg: #DBEAFE;`.

**Rejection buckets and all counts render as plain slate-900/`--text-muted` text** — no additional colors.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA (this page) | "Run discovery" |
| Trigger success flash | "Discovery run queued." |
| Trigger server error flash | "Something went wrong. Your action was not completed — please try again." (Phase 1 server-error copy, reuse verbatim) |
| Queue note beside button | "Queued runs execute in order." |
| Runs empty state — heading | "No discovery runs yet" |
| Runs empty state — body | "Trigger a run to start collecting business leads from compliant sources. Per-source metrics and qualified leads will appear here." (Run discovery button remains visible above) |
| Leads empty state — heading | "No qualified leads yet" |
| Leads empty state — body | "Leads appear here once runs complete and candidates pass normalization, deduplication, and enrichment." |
| Zero-sources banner | "No discovery sources are enabled. Enable at least one source in configuration (for example `SOURCE_HN_ENABLED`) to collect leads." |
| Runs limit note | "Showing the most recent 10 runs." |
| Leads limit note | "Showing the most recent 20 leads. The full lead list arrives with the Next.js dashboard." |
| Run status labels | "In progress" · "Complete" · "Partial" · "Failed" |
| Source status labels | "OK" · "Empty" · "Blocked" · "Error" · "Excluded" · "Disabled" |
| Trigger labels | "Manual" · "Scheduled" |
| Rejection bucket labels | display the raw bucket key: `missing_name`, `missing_website`, `malformed`, `too_short`, `blocked`, `disabled` (RESEARCH `RejectReason`) |

**Destructive actions in this phase:** none — no deletes, no stop/cancel of runs. The trigger is non-destructive (queued, serially executed).

---

## Component Specs

All Phase 1 primitives are reused as-is (`.btn*`, `.card`, `.input`, `.badge` + variants, `.table`, `.flash--*`, `.nav*`, `.empty-state`, `.detail-list`, `.page-header`, `.mono-payload`, `.badge--action`, `.visually-hidden`). The complete Phase 2 CSS delta:

| Primitive (new) | Appearance | Phase 2 target |
|-----------------|------------|----------------|
| `.table-scroll` | `overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface);` wrapper around wide tables (runs table) | Table wrapper |
| `.num` | `text-align: right; font-variant-numeric: tabular-nums;` — applied to count/ratio cells (per-source cells, New, Merged, Duration, Requests, Found, Parsed OK, Rejected, totals) | numeric table cells |
| `.badge--running` | `color: var(--blue-text); background: var(--blue-bg);` | Badge |
| `.badge--complete` | same as `.badge--approved` (green pair) — semantic alias | Badge |
| `.badge--partial` | same as `.badge--pending` (amber pair) — semantic alias | Badge |
| `.badge--failed` | same as `.badge--rejected` (red pair) — semantic alias | Badge |
| `.badge--ok` | same as `.badge--approved` — semantic alias | Badge |
| `.badge--empty` | same as `.badge--pending` — semantic alias | Badge |
| `.badge--blocked` | same as `.badge--rejected` — semantic alias | Badge |
| `.badge--error` | same as `.badge--escalated` (violet pair) — semantic alias | Badge |
| `.badge--excluded` / `.badge--disabled` | same as `.badge--expired` (slate pair) — semantic aliases | Badge |
| `.badge--source` | identical treatment to `.badge--action`: `color: var(--text-muted); background: var(--bg); border: 1px solid var(--border);` — declared separately for lineage semantics | Badge |
| `.banner` | page-level note: `background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--amber-text); color: var(--text); padding: var(--space-md); border-radius: var(--radius-md); margin-bottom: var(--space-lg);` (existing tokens only) | Banner |

**Reuse (unchanged) pattern notes:** metrics/leads tables use `.table` inside `.table-scroll`; expanders use `<details>/<summary>` with the queue-details affordance (accent summary); rejections and structured lead fields use `.detail-list`; run ID uses the 13px mono face inside the expander.

---

## Page Anatomy — discovery.html

### Runs table (newest first, limit 10)

Columns (fixed set — one per registered adapter in registry order: HN, Reddit, Yelp, G Maps, Mock):

| Col | Content | Notes |
|-----|---------|-------|
| Started | `YYYY-MM-DD HH:MM UTC` | server-formatted, never raw |
| Trigger | `.badge--action` — "Manual" / "Scheduled" | D-28 trigger_source |
| Status | run status badge (In progress / Complete / Partial / Failed) | |
| HN / Reddit / Yelp / G Maps / Mock | `parsed/found` compact, e.g. `12/15`; `—` when source disabled/excluded that run | `.num` alignment; per-source stats from `discovery_run_source_stats` (RESEARCH Pattern 2) |
| New | count of new master records from this run | `.num` |
| Merged | count of merges into existing masters (dedup, D-25) | `.num` |
| Duration | `45s` · `2m 14s` · `1h 03m`; **"In progress"** for RUNNING | finished − started, server-formatted; never raw floats |

`<tfoot>` totals row: Started cell = "Totals" (600 weight); per-source cells = source-level found totals; New/Merged = Σ; Duration cell = "Dedup rate 34%" (`merged / (new + merged)`, server-computed; render `—` when no candidates). Per-source totals omit the `parsed/found` slash — the cell shows the source's total found.

Row expander — `<details>` `<summary>` "Source details" per run, containing:
- Run ID at 13px mono (full UUID — the row's public ID; correlation_id is NEVER displayed, Phase 1 rule).
- Per-source stat table: Source (display name) · Status (source badge) · Requests · Found · Parsed OK · Rejected · New · Merged — all `.num` except Source/Status.
- Rejection buckets: under the Rejected cell, a 14px muted line "`missing_website 4 · too_short 2`" (bucket `·` count, joined by ` · `); `—` when no rejections.
- Invariants (`found == parsed + rejected`, `new + merged == parsed`) are guaranteed by tests and NOT rendered.

### Leads table (newest first by first-discovered date, limit 20)

| Col | Content | Notes |
|-----|---------|-------|
| Name | lead name (master record) | |
| Industry | normalized industry string | `—` when missing |
| Location | city/region string | `—` when missing |
| Source lineage | one `.badge--source` per distinct source in the master's lineage (e.g. `HN` `Yelp`) — multiple badges = same business found by multiple sources (success criterion 2 is visible here) | ordered by registry order |
| Enrichment | `n/10` — filled fields of the 10-field LEAD-02 set (name, industry, website, email, phone, location, employees, reviews, ratings, tech stack) | `.num`; server-computed |
| Found | `YYYY-MM-DD` of the run that first created the master record | |
| Details | `<details>/<summary>` "View" (audit.html pattern) → `.detail-list`: Website, Email, Phone, Employees, Reviews, Ratings, Tech stack (comma-joined list) | structured fields only — never raw payload or sanitized text |

### Secondary states

- **No runs yet** → `.empty-state` (runs copy) replaces the runs table; leads section omitted entirely; action row + banner still render.
- **Runs exist, no leads** → runs table renders; `.empty-state` (leads copy) replaces the leads table.
- **Run in progress** → RUNNING badge ("In progress"), Duration cell "In progress", no finished timestamp; button stays enabled (extra triggers enqueue serially).
- **Partial source failure** → PARTIAL run badge; expander shows source rows with Blocked/Error badges and rejection bucket lines (LEAD-04 visible: Excluded/Blocked sources appear as rows, never silently).
- **Zero sources enabled** → `.banner` with the zero-sources copy above the runs section; runs still triggerable (they will record DISABLED/EXCLUDED per-source rows and audit events).

---

## View Model Contract (GET /discovery — structured-only, T-03-01 pattern)

The route passes a single pre-shaped context dict; the template performs NO data computation, no date/format math, no aggregation:

- `enabled_source_count: int` — zero ⇒ render banner
- `runs: [{id, started_at, duration_display, status, status_label, trigger_label, sources: [{source_id, display_name, status, status_label, requests_made, found, parsed_ok, rejected, new_count, merged_count, rejection_buckets: [{reason, count}]}], totals: {found, new, merged}, dedup_rate_display}]` — newest first, `duration_display` already "In progress" or formatted; per-source list in registry order, disabled/excluded sources included with their status
- `source_columns: [{source_id, short_name}]` — registry order (HN, Reddit, Yelp, G Maps, Mock); drives both the fixed per-source columns and the expander rows; per-run `sources` entries keyed by `source_id`
- `leads: [{id, name, industry, location, website_url, email, phone, employee_count_display, rating_display, review_count, tech_stack: [str], enrichment_display, found_date, lineage: [{source_id, short_name}]}]` — newest first; every value pre-formatted for display (rating one decimal "4.5", employees "10–50" or integer, enrichment "7/10")
- `flash` — existing cookie-flash mechanism (`read_flash`/`set_flash`, unchanged)
- All scraped-derived values arrive sanitized (CMP-06) and are rendered under Jinja2 autoescape — `|safe` is forbidden on any field sourced from scraping or enrichment.

---

## Interaction Contract

- **Zero client JS** (D-29, locked). All mutations are HTML form POSTs; expanders are `<details>/<summary>`.
- **Trigger** (`POST /discovery/run`): `Depends(get_current_owner)` + `_check_origin(request)` (T-03-03 pattern from approvals.py); create `DiscoveryRun(trigger_source="MANUAL", status=RUNNING, correlation_id=uuid4())` + `OutboxEvent(topic="discovery.run")` + `AuditService.record(actor="owner", action="discovery_triggered")` in ONE transaction (RESEARCH Pattern 2 — short, enqueue-only); `set_flash(response, "Discovery run queued.", kind="success")`; 302 → `/discovery`. Form: `<form method="post" action="/discovery/run"><button type="submit" class="btn btn-primary">Run discovery</button></form>`.
- **Nav** ("Discovery" link) → `GET /discovery`, active-state via the existing `active_page` block variable.
- **Scheduled runs** (D-12 daily job, RESEARCH Pattern 2) render identically with "Scheduled" trigger badge — no UI difference beyond the label.
- **Log out / session expiry / flash auto-dismiss**: Phase 1 behavior unchanged.

---

## Accessibility (WCAG 2.1 AA — Phase 1 baseline, unchanged + additions)

- All text/background pairs ≥ 4.5:1 — the one new pair (blue-700/blue-100) verified ≈ 5.5:1.
- Badges always carry text labels (never color-only); rejection buckets are plain text.
- `<th scope="col">` on both tables; first column of each table uses `<th scope="row">`; both tables carry `aria-label` ("Discovery run history", "Qualified leads").
- `<details>/<summary>` affordances remain keyboard-operable; `:focus-visible` ring on every interactive element (Phase 1 rule).
- Wide runs table: `.table-scroll` wrapper provides horizontal scroll — no hover-only affordances, no clipped content below 960px.
- Form labels via `for`/`id`; `lang="en"`, per-page `<title>` ("Discovery — AI Agency OS"), skip-to-main link (existing).
- Jinja2 autoescape on; all scraped/enriched fields escaped at render (never `|safe`).

---

## Security-Adjacent UI Rules (Phase 1 locked decisions, apply unchanged)

- `/discovery` + `/discovery/run` are owner-only (`get_current_owner`); the run worker executes as `system` actor (RESEARCH §Security Domain).
- `_check_origin` on the mutating POST; SameSite=Lax session cookie (D-16).
- **correlation_id and thread IDs are never displayed** — the run's correlation_id (D-07) stays server-side; only the run UUID (public row ID) renders, in the expander.
- The UI renders structured normalized fields only — never raw source payloads, never `sanitized_text` free prose (CMP-06 + T-03-01); Jinja autoescape is the last line of defense, not the first.
- No public write endpoints in this phase's surface.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not applicable — shadcn not initialized (D-17/D-29: Jinja2 SSR continuation; Next.js + shadcn deferred beyond this slice) |

No third-party registries, no component packages, no icon packages. Registry vetting gate: not applicable (RESEARCH §Package Legitimacy Audit: zero new dependencies).

---

## Forward Compatibility

- All Phase 1 mappings hold unchanged: spacing = Tailwind `p-1…p-16`; type = `text-sm/base/xl/2xl`; colors = stock Tailwind tokens — including the new `--blue-text/--blue-bg` pair (`blue-700`/`blue-100`, stock).
- New primitives map mechanically: `.table-scroll` → wrapper div; `.num` → `text-right tabular-nums`; badge variants → `Badge variant` props; `.banner` → `Alert`/`Banner`.
- Migration rule (Phase 1): the future Next.js phase replaces `app.css` wholesale — this phase only ADDS primitives to it.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending

---

*Phase: 02-discovery*
*Generated: 2026-08-05*
*Sources: 1-UI-SPEC.md (tokens verbatim, approved c7f47d5), 02-CONTEXT.md (D-21..D-30), 02-RESEARCH.md (§Recommended Project Structure, Patterns 2/4, Pitfalls 1/4/5, Code Examples — trigger endpoint + flash copy), ROADMAP.md Phase 2 success criteria 1-2, backend/templates/{base,approvals,audit}.html + app.css (existing primitives)*
