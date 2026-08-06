# Requirements: AI Agency OS

**Defined:** 2026-08-04
**Core Value:** A self-operating agency pipeline that discovers qualified opportunities, converts them through an autonomous sales/legal/finance loop, delivers projects, and locks in recurring revenue — with human approval only at defined gates.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation

- [x] **FND-01**: Owner can run the backend as an installable Python package (`pip install -e .`) with the flat `backend/` package layout, `__init__.py` files, and a README that installs and runs it
- [x] **FND-02**: All declared dependencies in `pyproject.toml` are current (FastAPI, redis, supabase, playwright, httpx, langgraph 1.x, stripe 15.x, razorpay 2.x) with `sqlalchemy` added and a `uv.lock` committed
- [x] **FND-03**: Owner can run database migrations via Alembic (replaces `create_all`) against PostgreSQL/Supabase
- [x] **FND-04**: Every AI agent action, decision, and external side effect is written to an append-only audit log with correlation IDs, queryable by lead/proposal/contract
- [x] **FND-05**: Owner can view, approve, reject, or escalate every approval-gated action (contracts, payments, below-floor offers, legal changes) from an approval queue
- [x] **FND-06**: Owner can set spending/budget caps (per-provider LLM cost, per-outreach volume) that hard-block exceeding sends/calls
- [x] **FND-07**: Scheduled jobs run on a heartbeat-monitored scheduler that alerts on silent failures

### Compliance

- [x] **CMP-01**: Crawler fetches respect robots.txt (deny-by-default) before crawling any domain
- [x] **CMP-02**: Crawler rate-limits per domain with token-bucket throttling and jitter
- [x] **CMP-03**: Outreach is rate-limited and cannot exceed anti-spam volume caps per sender/domain
- [x] **CMP-04**: Outreach requires consent records or a documented lawful basis (India DPDP-aware) and one-click unsubscribe in every email
- [ ] **CMP-05**: Webhook ingestion (payments, delivery) is idempotent against replay (DB-level dedupe)
- [x] **CMP-06**: Prompt injection is mitigated at ingestion (scraped content sanitized, kept out of instruction context) with adversarial test fixtures

### Owner Dashboard

- [x] **DASH-01**: Owner can log in to a dashboard with session auth
- [x] **DASH-02**: Owner sees pipeline state: qualified leads, outreach status, proposals, contracts awaiting approval, active projects, MRR
- [x] **DASH-03**: Owner can review and act on audit log entries and approval requests from the dashboard

### Lead Discovery

- [x] **LEAD-01**: System collects business candidates from 3-5 high-yield compliant sources (e.g. Google Maps API/search, JustDial, Reddit/Indie Hackers/HN, job boards) with per-source rate limiting
- [x] **LEAD-02**: System enriches each lead with business data: name, industry, website, email, phone, location, employees, reviews, ratings, tech stack
- [x] **LEAD-03**: System deduplicates leads across sources (same business merged once)
- [x] **LEAD-04**: System excludes platforms/businesses that block automated collection (no ToS-violating scraping)
- [x] **LEAD-05**: Owner can run discovery on demand (manual trigger) and see per-run parse-success metrics

### Website Intelligence

- [x] **AUDT-01**: System audits a business website: performance, accessibility, SEO, mobile scores (INP-based Core Web Vitals, not FID)
- [x] **AUDT-02**: System detects tech stack, CMS, hosting provider, and analytics presence
- [x] **AUDT-03**: System finds broken links, missing forms, and conversion-flow gaps
- [x] **AUDT-04**: System stores audit results per lead with timestamped history

### Opportunity Detection

- [ ] **OPP-01**: System detects automation opportunities per industry (booking, appointments, admissions, onboarding, invoicing) with pattern rules
- [ ] **OPP-02**: System detects AI opportunities (missing chatbot, FAQ assistant, CRM, analytics, knowledge base)
- [ ] **OPP-03**: System estimates ROI for each detected opportunity and ranks them

### Lead Scoring

- [ ] **SCOR-01**: System scores each lead 0-100 with weighted factors (website quality, SEO, growth signals, size, automation potential, AI potential, budget)
- [ ] **SCOR-02**: System maintains a priority queue of qualified leads with scores, surfaced to the sales pipeline

### Sales Agent

- [ ] **SALE-01**: System generates personalized outreach (email) from business research, within brand guidelines and deliverability infrastructure (SPF/DKIM/DMARC-ready, warmup-aware)
- [ ] **SALE-02**: System sends follow-up sequences with configurable cadence and caps
- [ ] **SALE-03**: System handles common objections from a predefined response library
- [ ] **SALE-04**: System logs every outreach action to the audit log with unsubscribe/consent state

### Proposal Generator

- [ ] **PROP-01**: System generates a proposal from an audit + opportunity analysis: exec summary, audit report, scope, timeline, pricing, FAQs, terms, next steps
- [ ] **PROP-02**: Proposal pricing is computed by the pricing engine (not freeform LLM pricing)

### Pricing Engine

- [ ] **PRIC-01**: System computes recommended/minimum/target prices, max discount, and margin from hours, complexity, market rate, industry, size, expected ROI, and close-rate inputs
- [ ] **PRIC-02**: Owner can configure service packages and pricing rules (websites, automations, chatbots, custom AI) that the engine must respect

### Negotiation Agent

- [ ] **NEGO-01**: Negotiation agent enforces price floors via code-validated tool calls (never below minimum price), escalating below-floor offers to the approval gate
- [ ] **NEGO-02**: Negotiation agent never promises unsupported features or modifies legal clauses (escalates unusual requests to human approval)
- [ ] **NEGO-03**: Negotiation follows the anchor → ROI → bundle → maintenance → final discount → close strategy and logs the full trail

### Contracts & Legal

- [ ] **CONT-01**: System generates proposal → statement of work → contract from approved templates with variable substitution
- [ ] **CONT-02**: System generates optional NDA and invoice with payment schedule
- [ ] **CONT-03**: No contract or payment executes without explicit human approval; approval status is tracked and audited

### Finance & Payments

- [ ] **FINA-01**: System creates invoices from approved contracts with payment schedules
- [ ] **FINA-02**: System collects payments via Razorpay/Stripe (one-time and recurring) with webhook idempotency and reconciliation
- [ ] **FINA-03**: System sends automated payment reminders and tracks invoice status
- [ ] **FINA-04**: Owner can view MRR/ARR, pipeline value, gross margin per service, and client LTV/CAC

### Project Delivery

- [ ] **PROJ-01**: System creates a project from a signed contract with generated tasks and a timeline
- [ ] **PROJ-02**: System generates client-facing deliverables: website/automation/chatbot per service scope (design → development → testing → deploy)
- [ ] **PROJ-03**: System deploys client projects to configured targets (Vercel/Cloudflare/Netlify/Railway/VPS) with analytics, SEO, sitemap, robots.txt auto-configured
- [ ] **PROJ-04**: System runs QA before delivery: automated tests, accessibility (WCAG 2.1 AA), performance checks, security scanning

### Maintenance & Growth

- [ ] **MAINT-01**: System runs monthly maintenance checks (SSL, uptime, broken links, SEO, security, dependency updates) per client site
- [ ] **MAINT-02**: System generates and sends monthly maintenance reports to clients automatically
- [ ] **GROW-01**: System identifies upsell opportunities from client usage/health data and generates upsell proposals
- [ ] **GROW-02**: System requests referrals from happy clients on schedule

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Discovery Expansion

- **LEAD-06**: Additional sources (IndiaMART, GoodFirms, Clutch, Product Hunt, Crunchbase) behind provider-specific compliance review
- **LEAD-07**: Email/contact verification provider integration (bounce-risk checks) with 30-90 day re-verification

### Sales Expansion

- **SALE-05**: LinkedIn outreach via official API or approved partner path only (human-in-the-loop)
- **SALE-06**: WhatsApp outreach with template approval + opt-in management
- **SALE-07**: Meeting scheduling integration (Cal.com/Calendly)

### Delivery Expansion

- **PROJ-05**: AI chatbot/dashboard delivery products (LangChain/LangGraph based client builds)
- **PROJ-06**: n8n-based automation delivery service with multi-tenant isolation

### Intelligence Expansion

- **SCOR-03**: Score calibration against actual close rates (feedback loop)
- **AUDT-05**: Field-data (RUM) Core Web Vitals vs lab scores reconciliation
- **GROW-03**: Churn prediction and client health scoring model

## Out of Scope

| Feature | Reason |
|---------|--------|
| LinkedIn/Instagram/Facebook/X direct automation | ToS violations (hiQ/ProAPIs precedent); official-API-only or human-in-loop paths deferred to v2 |
| Purchased lead lists | DPDP exposure (up to ₹250 crore penalties); violates consent-based sourcing |
| Bulk cold-email without consent | CAN-SPAM ($53K+/email) and India DPDP (no legitimate-interest marketing basis); consent records mandatory in v1 |
| WhatsApp bulk blasting | Requires template approval + opt-in + quality tiers; gated to v2 |
| CAPTCHA bypass / stealth scraping | DMCA §1201 exposure; logged-out compliant collection only |
| Mobile app development for clients | No delivery pipeline defined; revisit post-stability |
| White-label/partner offerings | Post-pilot territory |
| Full autonomous operation (<2 hrs human/week) | Post-pilot target; approval gates remain in v1 |
| Kafka/event-store infrastructure | Postgres outbox + asyncio worker suffices for single-operator scale |
| Temporal/Celery workers | Overweight for async-stack + free-tier solo operation; APScheduler + outbox chosen |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 1 | Complete |
| FND-02 | Phase 1 | Complete |
| FND-03 | Phase 1 | Complete |
| FND-04 | Phase 1 | Complete |
| FND-05 | Phase 1 | Complete |
| FND-06 | Phase 1 | Complete |
| FND-07 | Phase 1 | Complete |
| CMP-01 | Phase 1 | Complete |
| CMP-02 | Phase 1 | Complete |
| CMP-03 | Phase 1 | Complete |
| CMP-04 | Phase 1 | Complete |
| CMP-05 | Phase 4 | Pending |
| CMP-06 | Phase 2 | Complete |
| DASH-01 | Phase 1 | Complete |
| DASH-02 | Phase 2 | Complete |
| DASH-03 | Phase 1 | Complete |
| LEAD-01 | Phase 2 | Complete |
| LEAD-02 | Phase 2 | Complete |
| LEAD-03 | Phase 2 | Complete |
| LEAD-04 | Phase 2 | Complete |
| LEAD-05 | Phase 2 | Complete |
| AUDT-01 | Phase 02.1 | Complete |
| AUDT-02 | Phase 02.1 | Complete |
| AUDT-03 | Phase 02.1 | Complete |
| AUDT-04 | Phase 02.1 | Complete |
| OPP-01 | Phase 02.2 | Pending |
| OPP-02 | Phase 02.2 | Pending |
| OPP-03 | Phase 02.2 | Pending |
| SCOR-01 | Phase 02.2 | Pending |
| SCOR-02 | Phase 02.2 | Pending |
| SALE-01 | Phase 3 | Pending |
| SALE-02 | Phase 3 | Pending |
| SALE-03 | Phase 3 | Pending |
| SALE-04 | Phase 3 | Pending |
| PROP-01 | Phase 3 | Pending |
| PROP-02 | Phase 3 | Pending |
| PRIC-01 | Phase 3 | Pending |
| PRIC-02 | Phase 3 | Pending |
| NEGO-01 | Phase 3 | Pending |
| NEGO-02 | Phase 3 | Pending |
| NEGO-03 | Phase 3 | Pending |
| CONT-01 | Phase 4 | Pending |
| CONT-02 | Phase 4 | Pending |
| CONT-03 | Phase 4 | Pending |
| FINA-01 | Phase 4 | Pending |
| FINA-02 | Phase 4 | Pending |
| FINA-03 | Phase 4 | Pending |
| FINA-04 | Phase 4 | Pending |
| PROJ-01 | Phase 5 | Pending |
| PROJ-02 | Phase 5 | Pending |
| PROJ-03 | Phase 5 | Pending |
| PROJ-04 | Phase 5 | Pending |
| MAINT-01 | Phase 6 | Pending |
| MAINT-02 | Phase 6 | Pending |
| GROW-01 | Phase 6 | Pending |
| GROW-02 | Phase 6 | Pending |

**Coverage:**

- v1 requirements: 56 total
- Mapped to phases: 56
- Unmapped: 0 ✓

---
*Requirements defined: 2026-08-04*
*Last updated: 2026-08-04 after roadmap traceability assignment*
