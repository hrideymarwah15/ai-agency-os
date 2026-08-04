# Roadmap: AI Agency OS

## Overview

From a broken Python skeleton to a self-operating agency pipeline. Phase 1 repairs and hardens the foundation and builds the trust mechanism — installable package, current dependencies, migrations, append-only audit log, budget caps, heartbeat-monitored scheduler, compliance middleware (robots.txt, rate limits, anti-spam, consent), session auth, and the LangGraph approval gate with an owner-facing approval queue. Phase 2 delivers the first value: compliant lead discovery from 3-5 sources, website intelligence audits, ROI-quantified opportunity detection, weighted lead scoring, and the owner's pipeline view. Phase 3 converts qualified leads into money-adjacent assets: pricing engine, guardrailed negotiation, compliant outreach sequences, and proposals. Phase 4 executes deals: approval-gated contracts, idempotent payments, and the finance dashboard. Phase 5 delivers projects: contract-to-project creation, QA-gated builds, and deployment with auto-config. Phase 6 closes the loop: monthly maintenance, automated client reports, upsells, and referrals — locking in recurring revenue. Human approval remains the floor at every gate (contracts, payments, commitments outside pricing rules).

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation & Orchestration Core** - Repairs (package/deps/migrations), compliance middleware, audit log, budget caps, scheduler, LangGraph approval gate, owner login + approval queue
- [ ] **Phase 2: Discovery** - Compliant lead collection, website intelligence, opportunity detection, lead scoring, pipeline view
- [ ] **Phase 3: Sales** - Pricing engine, guardrailed negotiation, outreach sequences, proposal generator
- [ ] **Phase 4: Legal + Finance** - Approval-gated contracts/NDA/invoices, idempotent payments, finance dashboard
- [ ] **Phase 5: Delivery** - Contract-to-project, QA-gated deliverables, deployment with auto-config
- [ ] **Phase 6: Maintenance + Growth** - Monthly checks, client reports, upsell proposals, referral requests

## Phase Details

### Phase 1: Foundation & Orchestration Core

**Goal**: The platform's plumbing is production-ready and the owner's trust mechanism works end-to-end: installable package, current declared dependencies, Alembic migrations, append-only audit log, hard budget caps, heartbeat-monitored scheduler, compliance middleware (robots.txt, per-domain rate limits, anti-spam caps, consent/suppression), session auth, and a LangGraph approval engine with an owner-facing approval queue that pauses and resumes agent workflows.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03, FND-04, FND-05, FND-06, FND-07, CMP-01, CMP-02, CMP-03, CMP-04, DASH-01, DASH-03
**Success Criteria** (what must be TRUE):

  1. Owner can install and run the backend from a clean venv via `pip install -e .`, run `alembic upgrade head` against PostgreSQL/Supabase, and start the API — with all declared dependencies current and a committed `uv.lock` (no `create_all`, no missing deps)
  2. Owner can log in with session auth and review every AI agent action, decision, and external side effect in the append-only audit log, queryable by lead/proposal/contract correlation ID
  3. Owner can approve, reject, or escalate every approval-gated action (contracts, payments, below-floor offers, legal changes) from the approval queue; approving resumes the paused agent workflow, rejecting halts it — and the round-trip is proven with the existing CEO/LeadHunter agents
  4. LLM spend and outreach volume can never exceed the owner's configured caps — cap-exceeding calls/sends are hard-blocked and logged; scheduled jobs heartbeat and alert the owner on silent failure
  5. Every fetch path consults robots.txt (deny-by-default) with per-domain token-bucket rate limiting; outreach sends enforce anti-spam volume caps, require consent records, and consult the suppression list — one-click unsubscribe removes recipients from future sends

**Plans**: 5 plans
**UI hint**: yes
Plans:
**Wave 1**

- [ ] 01-01-PLAN.md — Walking Skeleton: package + deps + uv.lock, Alembic migrations, app boot, owner login, DB-backed audit route (Wave 0 tests + CI)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-02-PLAN.md — Append-only audit log: AuditService query, immutability trigger, /audit correlation filter page
- [ ] 01-04-PLAN.md — Budget caps + scheduler: atomic LLM/outreach counters, call_llm gate, heartbeat scheduler

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 01-05-PLAN.md — Compliance middleware: robots deny-by-default, token-bucket rate limits, send gates, one-click unsubscribe

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 01-03-PLAN.md — Approval engine capstone: LangGraph interrupt gate over CEO/LeadHunter, approval queue UI, sweeper

### Phase 2: Discovery

**Goal**: The system finds, enriches, audits, and qualifies real business leads from compliant sources, detects ROI-quantified opportunities, scores them into a priority queue, and the owner sees the resulting pipeline state in the dashboard — with scraped content kept out of instruction context at ingestion.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: LEAD-01, LEAD-02, LEAD-03, LEAD-04, LEAD-05, AUDT-01, AUDT-02, AUDT-03, AUDT-04, OPP-01, OPP-02, OPP-03, SCOR-01, SCOR-02, DASH-02, CMP-06
**Success Criteria** (what must be TRUE):

  1. Owner can trigger discovery on demand and see per-run parse-success metrics per source; runs collect candidates from 3-5 compliant sources with per-source rate limiting, and platforms/businesses that block automated collection are excluded, not scraped
  2. Owner sees deduplicated, enriched leads (name, industry, website, email, phone, location, employees, reviews, ratings, tech stack) with source lineage — the same business from multiple sources appears exactly once
  3. Owner can view a website audit per lead (performance, accessibility, SEO, mobile with INP-based Core Web Vitals; tech stack, CMS, hosting, analytics; broken links and missing forms) with timestamped history
  4. Owner sees each lead's detected automation and AI opportunities with ROI estimates, ranked, plus a weighted 0-100 lead score and priority ordering — surfaced in the dashboard pipeline view
  5. Scraped content cannot inject instructions into agent prompts: ingestion sanitization keeps content out of instruction context and adversarial injection test fixtures pass

**Plans**: TBD
**UI hint**: yes

### Phase 3: Sales

**Goal**: Qualified leads become priced, personalized opportunities: compliant outreach and follow-up sequences, deterministic pricing from configurable packages, code-guardrailed negotiation with escalation, and proposals generated from audits, opportunities, and engine-computed pricing — every action audited.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SALE-01, SALE-02, SALE-03, SALE-04, PROP-01, PROP-02, PRIC-01, PRIC-02, NEGO-01, NEGO-02, NEGO-03
**Success Criteria** (what must be TRUE):

  1. Owner can launch personalized outreach emails (within brand guidelines, consent + one-click unsubscribe + lawful basis in every message, volume caps enforced in code) and follow-up sequences with configurable cadence and caps; every outreach action is audit-logged with unsubscribe/consent state
  2. Owner can configure service packages and pricing rules that the pricing engine deterministically respects — recommended/minimum/target prices, max discount, and margin computed from hours, complexity, market, industry, size, ROI, and close-rate inputs (never freeform LLM pricing)
  3. Negotiation can never commit below the code-enforced price floor or promise unsupported features; below-floor offers and unusual requests are escalated to the owner's approval queue (approval engine), and the full anchor → ROI → bundle → maintenance → discount → close trail is logged
  4. Owner can generate a proposal from audit + opportunity analysis (exec summary, audit report, scope, timeline, pricing, FAQs, terms, next steps) with pricing engine output embedded
  5. Common objections are answered from the predefined response library, and replies the agent cannot classify with confidence are escalated to the owner

**Plans**: TBD
**UI hint**: yes

### Phase 4: Legal + Finance

**Goal**: Approved deals become money: contracts, SOWs, NDAs, and invoices generated from approved templates with variable substitution, human approval gates enforced before any contract or payment executes, payments collected via Razorpay/Stripe with idempotent webhooks, automated reminders, and the owner sees MRR/ARR, pipeline value, margins, and LTV/CAC.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: CONT-01, CONT-02, CONT-03, FINA-01, FINA-02, FINA-03, FINA-04, CMP-05
**Success Criteria** (what must be TRUE):

  1. Owner can generate proposal → statement of work → contract (plus optional NDA and invoice with payment schedule) from approved templates with variable substitution
  2. No contract or payment executes without explicit owner approval — approval status is tracked, audited, and visible in the approval queue; owner can approve or reject before anything is sent or charged
  3. Owner can collect one-time and recurring payments via Razorpay/Stripe with invoices created from approved contracts; replayed or retried webhooks never double-credit or double-charge (DB-level idempotency)
  4. System sends automated payment reminders and owner can see invoice status per client, with reconciliation against the provider balance
  5. Owner can view finance metrics in the dashboard: MRR/ARR, pipeline value, gross margin per service, and client LTV/CAC

**Plans**: TBD
**UI hint**: yes

### Phase 5: Delivery

**Goal**: Signed contracts become delivered, QA-gated projects: project creation with generated tasks and timeline, client-facing deliverables built per service scope (design → development → testing → deploy), and deployment to configured targets with analytics, SEO, sitemap, and robots.txt auto-configured.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: PROJ-01, PROJ-02, PROJ-03, PROJ-04
**Success Criteria** (what must be TRUE):

  1. Owner can create a project from a signed contract — tasks and timeline are generated automatically from the service scope
  2. System produces client-facing deliverables per service scope (website/automation/chatbot) through design → development → testing → deployment
  3. System deploys client projects to configured targets (Vercel/Cloudflare/Netlify/Railway/VPS) with analytics, SEO, sitemap, and robots.txt auto-configured
  4. No deliverable ships without passing QA: automated tests, accessibility (WCAG 2.1 AA), performance checks, and security scanning — failing deliverables are blocked and the QA result is recorded per deliverable

**Plans**: TBD

### Phase 6: Maintenance + Growth

**Goal**: Delivered clients stay healthy and become recurring revenue: monthly maintenance checks with automated white-label client reports, upsell proposals from usage/health data, and scheduled referral requests — all on the heartbeat-monitored scheduler.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: MAINT-01, MAINT-02, GROW-01, GROW-02
**Success Criteria** (what must be TRUE):

  1. System runs monthly maintenance checks (SSL, uptime, broken links, SEO, security, dependency updates) per client site on the heartbeat-monitored scheduler, alerting on silent failures
  2. System generates and sends monthly maintenance reports to clients automatically (white-label, branded)
  3. System identifies upsell opportunities from client usage/health data and generates upsell proposals
  4. System requests referrals from happy clients on schedule

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Orchestration Core | 0/TBD | Not started | - |
| 2. Discovery | 0/TBD | Not started | - |
| 3. Sales | 0/TBD | Not started | - |
| 4. Legal + Finance | 0/TBD | Not started | - |
| 5. Delivery | 0/TBD | Not started | - |
| 6. Maintenance + Growth | 0/TBD | Not started | - |
