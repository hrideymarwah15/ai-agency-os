---
phase: 1
slug: foundation-orchestration-core
status: approved
reviewed_at: 2026-08-05
shadcn_initialized: false
preset: none
created: 2026-08-05
---

# Phase 1 — UI Design Contract (Foundation & Orchestration Core)

> Visual and interaction contract for the Phase 1 owner-facing UI: a minimal, server-rendered FastAPI + Jinja2 control surface (locked D-17) covering login, the approval queue, the read-only audit log, and one-click unsubscribe. No build step, no client JS, no external assets. Design tokens are defined to map 1:1 onto the Phase 2 Tailwind v4 + shadcn direction so migration is mechanical (see Forward Compatibility).

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none — hand-rolled CSS in a single stylesheet (`backend/static/app.css`), plain CSS custom properties; shadcn init deferred to Phase 2 (D-17, SUMMARY.md) |
| Preset | not applicable — tokens below intentionally mirror Tailwind v4 default palette/scale |
| Component library | none — CSS class primitives named to mirror shadcn components (see Component Inventory) |
| Icon library | none — text labels + status badges only; zero external assets, zero build step |
| Font | system-ui stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` (equals Tailwind v4 default sans — no webfont loading) |
| CSS delivery | one static stylesheet, CSS custom properties (`:root`), no preprocessor, no bundler |

## Pages in Scope

| Route | Template | Requirement | Purpose |
|-------|----------|-------------|---------|
| `GET /auth/login` | `login.html` | DASH-01 | Email + password form; POST sets signed session cookie |
| `GET /approvals` | `approvals.html` | FND-05, DASH-03 | Approval queue with Approve / Reject / Escalate per request |
| `GET /audit` | `audit.html` | FND-04, DASH-03 | Read-only audit log, filterable by correlation ID |
| `GET /unsubscribe?t=<token>` | `unsubscribe.html` | CMP-04 | Public, token-gated one-click unsubscribe confirmation |

No dashboard analytics in Phase 1 (DASH-02 → Phase 2). Landing page after login: `/approvals`. Any 401 on a protected route → redirect to `/auth/login` with flash "Your session has expired. Please log in again."

---

## Layout Contract

- **Top nav bar** (secondary surface `#FFFFFF`, 1px bottom border `#E2E8F0`): `agency_name` (from settings) on the left; nav links "Approval Queue" and "Audit Log"; owner email + "Log out" (a POST form button) on the right. Active nav link = accent color + 2px bottom accent border. Queue link shows pending count in a badge when > 0.
- **Main content**: single column, `max-width: 960px`, centered, `padding: 32px 16px 48px`. Page header pattern = Display title + body-size muted description (one line).
- **Login page**: 400px card, vertically + horizontally centered, brand name as Display text above the form, no registration link (single owner).
- **Table pages** (queue, audit): page header → filter/summary row → table → empty state (when applicable).
- **Primary visual anchor on /approvals**: the PENDING queue group with its accent Approve buttons; the nav pending-count badge is the secondary cue. No other element competes for the accent.
- No sidebar, no dashboard cards, no charts — deferred with the Next.js dashboard (Phase 2).

---

## Spacing Scale

Declared values (all multiples of 4 — matches Tailwind v4 spacing exactly):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Badge padding, icon gaps, `gap` in button-inline groups |
| sm | 8px | Table cell vertical padding (8px × 16px), form field gaps, nav link padding |
| md | 16px | Default element spacing, card padding, table cell horizontal padding, main-container side padding |
| lg | 24px | Section gaps, card-to-card gaps, form group separation, button min-height 36px (shadcn `h-9` default) |
| xl | 32px | Page-header to content gap, main top padding, queue-row gap |
| 2xl | 48px | Major section breaks, page bottom padding |
| 3xl | 64px | Page-level top spacing (rare) |

Exceptions: none. Buttons/inputs are 36px tall (fits the 4px grid); no 44px touch targets — desktop-only internal tool.

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Display (page titles, login brand) | 24px | 600 | 1.2 |
| Heading (section titles) | 20px | 600 | 1.2 |
| Body | 16px | 400 | 1.5 |
| Label/caption (form labels, badges, table cells, meta timestamps) | 14px | 400 | 1.4 |

Exactly 2 weights: regular (400) + semibold (600). No italic, no uppercase tracking for body text. Bold-style emphasis within body = 600 weight.

Exception (code face, not part of the 4-size scale): JSON payload previews render at **13px monospace** (`SF Mono, Menlo, Consolas, monospace`), escaped, inside `<pre>`.

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#F8FAFC` (slate-50) | Page background |
| Secondary (30%) | `#FFFFFF` | Cards, top nav bar, login panel, table surfaces |
| Border | `#E2E8F0` (slate-200) | 1px borders, row dividers, input borders |
| Text primary | `#0F172A` (slate-900) | Body, headings |
| Text secondary | `#475569` (slate-600) | Muted descriptions, meta, table secondary cells |
| Accent (10%) | `#2563EB` (blue-600) | See reserved list below |
| Destructive | `#DC2626` (red-600) | Reject button, destructive-flash text — nothing else |

**Accent is reserved for exactly:** primary action buttons ("Log in", "Approve"), the active nav link, inline text links, and the focus-visible ring. Never for: badges, borders, backgrounds, secondary text, table cells, or hover tints.

**Status badges** (text on tinted background, all pairs ≥ 4.5:1 AA):

| Status | Text / BG |
|--------|-----------|
| Pending | `#B45309` (amber-700) on `#FEF3C7` (amber-100) |
| Approved | `#15803D` (green-700) on `#DCFCE7` (green-100) |
| Rejected | `#B91C1C` (red-700) on `#FEE2E2` (red-100) |
| Escalated | `#7C3AED` (violet-600) on `#EDE9FE` (violet-100) |
| Expired | `#475569` (slate-600) on `#F1F5F9` (slate-100) |

**Flash messages:** success = `#15803D` text on `#F0FDF4`, border `#BBF7D0`; error = `#B91C1C` text on `#FEF2F2`, border `#FECACA`. Escalate button: ghost/secondary style (neutral border, neutral text) — neither accent nor destructive.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA (login) | "Log in" |
| Queue primary CTA | "Approve" (one per pending row) |
| Queue secondary CTAs | "Reject" · "Escalate" (one each per pending row) |
| Empty state — queue heading | "No approvals pending" |
| Empty state — queue body | "Nothing is waiting for your review. Gated actions (contracts, payments, below-floor offers, legal changes) will appear here when agents request them." |
| Empty state — audit heading | "No audit entries found" |
| Empty state — audit body | "Check the correlation ID and try again, or clear the filter to browse the full log." |
| Login error | "Invalid email or password." (uniform for wrong email vs wrong password — ASVS V2 timing mitigation) |
| Session expired | "Your session has expired. Please log in again." |
| Approve success flash | "Approved — {entity}. The agent workflow has resumed." |
| Reject success flash | "Rejected — {entity}. The workflow has been halted." |
| Escalate success flash | "Escalated — {entity}. Flagged for review." |
| Unsubscribe success | Heading "You have been unsubscribed" · body "You won't receive further messages from {agency_name}. If this was a mistake, contact {owner_email} to re-subscribe." |
| Unsubscribe invalid token | Heading "Invalid or expired link" · body "This unsubscribe link is invalid or has expired. Use the link from your latest message." |
| Server error (any form) | "Something went wrong. Your action was not completed — please try again." (details in server logs, never rendered) |

**Destructive actions in this phase** (each with confirmation approach):

| Action | Confirmation approach |
|--------|----------------------|
| Reject (queue) | Mandatory reason field in an inline expanding form (HTML `<details>` + `required`): "Rejecting halts the agent workflow and records your reason in the audit log. This cannot be undone." Submit disabled until a reason is entered. |
| Log out | Plain POST form button in nav (no confirm needed — re-login is trivial) |

---

## Component Inventory

CSS primitives (all in `app.css`, named to mirror shadcn components for Phase 2 mapping):

| Primitive | Appearance | Phase 2 target |
|-----------|------------|----------------|
| `.btn` base | 36px tall, radius 6px, 400 weight, 14px, inline-flex | Button |
| `.btn-primary` | Accent `#2563EB` bg, white text; hover darken 4% | Button variant default |
| `.btn-secondary` | White bg, slate-200 border, slate-900 text | Button variant outline |
| `.btn-destructive` | Destructive `#DC2626` bg, white text | Button variant destructive |
| `.btn-ghost` | No bg/border, slate-600 text; hover slate-100 bg | Button variant ghost |
| `.card` | White bg, 1px slate-200 border, radius 8px, padding 24px | Card |
| `.input` / `.label` / `.form-field` | 36px input, radius 6px, slate-200 border, 16px text; label 14px slate-600; `for`/`id` linked | Input / Label / Field |
| `.badge` + status variants | Radius 999px, 14px, tinted bg per Color table; **text label always present — color is never the sole indicator** | Badge |
| `.table` | Full width, th = 14px 600 slate-600 on `#F8FAFC`, td = 16px, row dividers slate-200, 8px/16px padding | Table |
| `.flash--success` / `.flash--error` | 16px, tinted bg + border per Color table, padding 16px, radius 8px | Alert |
| `.nav` / `.nav-link` / `.nav-link--active` | 16px links, active = accent + 2px bottom accent border | Top nav |
| `.empty-state` | Centered, 48px padding: 20px heading + 16px muted body | Empty state |
| `.detail-list` | Definition list of gated fields: 14px slate-600 labels, 16px values | DescriptionList |
| `.page-header` | Display title + muted one-line description | Heading + description |
| `.mono-payload` | 13px monospace `<pre>`, escaped JSON, slate-900 on `#F8FAFC`, radius 8px | Code block |

Interaction states (global): `:hover` darkens buttons 3–5%; `:focus-visible` = 2px accent ring with 2px offset on every interactive element; `:disabled` = 50% opacity + `cursor: not-allowed`.

---

## Interaction Contract

- **Zero client JS.** Every mutation is an HTML form POST; expandable details use `<details>`/`<summary>`; no inline scripts required (an optional ~5-line inline script may auto-dismiss flashes after 6s — progressive enhancement only).
- **Login** (`POST /auth/login`): success → 302 to `/approvals` with session cookie (HttpOnly, Secure per settings, SameSite=Lax, max-age = session TTL — flags locked by D-16); failure → 200 re-render with "Invalid email or password." flash. Fields: email (`autocomplete="username"`), password (`type="password"`, `autocomplete="current-password"`).
- **Queue rows** (`approvals.html`): PENDING requests first, oldest first, then decided requests most-recent-first. Summary line per row: status badge, action-type badge, entity name, amount (formatted 2dp with currency symbol from the gated action context — never raw floats), submitted timestamp. "View details" expander shows the full structured context (amount, entity, details fields) via `.detail-list` — **structured fields built by code, never raw LLM prose** (queue renders fields, not free text).
- **Queue actions**: Approve → immediate POST (no confirmation — it is the page's primary purpose). Reject → inline expanding form with mandatory reason (destructive styling). Escalate → ghost-button POST. All three: POST `/approvals/{id}/{approve|reject|escalate}`, CSRF-safe via SameSite=Lax + Origin header check (locked constraint), then 302 back to `/approvals` with the matching success flash; the row moves out of the PENDING group.
- **Audit log** (`audit.html`): read-only — zero action buttons. Filter form (correlation ID input + "Search" button) + clear-filter link. Newest first. Each row: timestamp, actor, action, entity type/ID; expander shows payload as escaped `.mono-payload` JSON. Empty filter = full log (success criterion 2: owner can review every action).
- **Unsubscribe** (`GET /unsubscribe?t=<token>`): no session required; valid signed token → success confirmation (CMP-04); invalid/expired token → "Invalid or expired link" state.
- **Log out**: POST form button in nav → clears cookie → redirect to `/auth/login`.

---

## Accessibility (WCAG 2.1 AA baseline)

- All text/background pairs in the Color contract ≥ 4.5:1 (verified in palette selection).
- Form labels associated via `for`/`id`; errors shown inline plus flash.
- `:focus-visible` ring on every interactive element (keyboard-operable queue actions — no hover-only affordances).
- Color never the sole status indicator: badges carry text labels ("Pending", "Approved", …).
- Table headers use `<th scope="col">`; data cells `<td>`.
- `lang="en"`, per-page `<title>`, meta viewport, skip-to-main link at top of nav.
- Rendered audit payloads and all user/agent-supplied fields are HTML-escaped (Jinja2 autoescape on; JSON via escaped `<pre>`) — the UI never renders unescaped LLM or web content.

---

## Security-Adjacent UI Rules (from locked decisions — non-negotiable)

- No public write endpoints in the UI surface except the token-gated unsubscribe route.
- Queue renders only structured context fields from `approval_requests` (D-09) — never LangGraph checkpoint internals and never raw LLM output; LLM output never sets the rendered decision value.
- Login error message is uniform for all credential failures.
- Logout is a POST, not a GET link.
- No secrets, tokens, or internal IDs beyond the row's public ID rendered in the UI; correlation IDs and thread IDs are never displayed.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none in Phase 1 | not applicable — shadcn not initialized (D-17); init gate runs in Phase 2 |

No third-party registries, no component packages, no icon packages in this phase. Registry vetting gate: not applicable.

---

## Forward Compatibility (Phase 2)

- **Spacing**: 4/8/16/24/32/48/64 = Tailwind `p-1 … p-16` exactly.
- **Typography**: 14/16/20/24px = `text-sm` / `text-base` / `text-xl` / `text-2xl`; weights = `font-normal` / `font-semibold`; font stack = Tailwind default sans.
- **Color**: every value is a stock Tailwind v4 slate/blue/red/amber/green/violet token (no custom hexes beyond the default scale).
- **Radius**: 6px / 8px / 999px = `rounded-md` / `rounded-lg` / `rounded-full`.
- **Structure**: top-nav + constrained-main layout survives into the Next.js app router shell; CSS primitives rename mechanically to shadcn imports (Button, Card, Input, Badge, Table, Alert).
- **Migration rule**: Phase 2 replaces `app.css` — it does not repair it.

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

*Phase: 01-foundation-orchestration-core*
*Generated: 2026-08-05*
*Sources: D-16/D-17/D-09/D-07 (CONTEXT.md), RESEARCH.md §Architecture/§Patterns, ROADMAP.md Phase 1 success criteria, REQUIREMENTS.md DASH-01/DASH-03/FND-04/CMP-04*
