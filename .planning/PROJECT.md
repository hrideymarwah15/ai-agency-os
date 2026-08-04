# AI Agency OS

## What This Is

An autonomous AI-powered digital agency platform that finds leads, qualifies prospects, generates personalized outreach, negotiates within predefined limits, creates contracts, delivers projects, collects payments, and manages clients with minimal human intervention. The owner defines services, pricing rules, brand guidelines, legal templates, and approval limits; the AI operates the rest — an AI company with specialized departments (agents) instead of a single AI agent. Target market: businesses needing websites, automations, AI chatbots, and custom internal AI systems.

## Core Value

A self-operating agency pipeline: continuously discover qualified opportunities → convert them through an autonomous sales/legal/finance loop → deliver projects and lock in recurring monthly revenue — all with human approval only at defined gates (contracts, payments, commitments outside pricing rules).

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Backend config system (pydantic-settings, ~50 env vars, service catalog + pricing multipliers) — existing
- ✓ Async SQLAlchemy/Supabase database layer with models + connection management — existing
- ✓ BaseAgent abstraction with LLM client (httpx: OpenRouter/Groq/Gemini), AgentContext, tool dispatch — existing
- ✓ CEO and Lead Hunter agent skeletons — existing
- ✓ 4 design specs (SPEC-001 core architecture, SPEC-002 lead discovery, SPEC-003 sales/proposal, SPEC-004 development pipeline) — existing
- ✓ `.planning/codebase/` map (7 docs) documenting as-built state — existing

### Active

<!-- Current scope. Building toward these. -->

- [ ] Market discovery engine: multi-source lead collection (search, directories, social, startup, community, job platforms) with enrichment
- [ ] Website intelligence crawler: performance/SEO/accessibility/UX scoring, tech-stack detection, broken links, conversion analysis
- [ ] Opportunity detector: automation + AI opportunity detection with ROI estimation per industry (restaurant, clinic, school, agency, etc.)
- [ ] Lead scoring engine: weighted multi-factor scoring (0-100) with priority queue
- [ ] Sales agent: personalized outreach, follow-ups, objection handling, meeting scheduling, CRM
- [ ] Proposal generator: exec summary, audit report, opportunity analysis, scope, timeline, pricing, FAQs, terms
- [ ] Pricing engine: hours/complexity/market/ROI inputs → price bounds, discount limits, margin
- [ ] Negotiation agent: guardrails (never below min price, no unsupported promises, no legal changes without approval), escalation
- [ ] Contract generator: proposal → SOW → contract → NDA → invoice, human approval gates
- [ ] Payment collection: Razorpay/Stripe, recurring billing, reminders, reconciliation
- [ ] Finance dashboard: MRR/ARR, pipeline value, margins, LTV/CAC
- [ ] Project management: contract → project, task generation, timeline, progress tracking
- [ ] Development pipeline: design → dev → testing → deployment (Vercel/Cloudflare/Netlify/Railway/VPS) with auto-config (analytics, forms, monitoring, SEO)
- [ ] QA department: unit/integration/e2e, accessibility (WCAG 2.1 AA), performance, security scanning
- [ ] Maintenance system: monthly checks (SSL, uptime, broken links, SEO, security, deps), automated client reports
- [ ] Upsell & referral engine: usage analytics, client health scoring, churn prediction
- [ ] Compliance & safety: robots.txt respect, rate limiting, anti-spam, auditable AI decision log
- [ ] Web dashboard / admin UI for owner oversight (approvals, pipeline, metrics)

### Out of Scope

- Mobile app development for clients — declared in PRD revenue list but no delivery pipeline defined; revisit after core is stable
- White-label/partner offerings — Phase 8.3 territory; requires post-MVP stabilization
- LinkedIn/Instagram/Facebook/X direct API integrations in v1 — platform restrictions; use compliant scraping/enrichment where terms allow
- Full human-like autonomous operation (<2 hrs/week human) — target for post-pilot state, not v1

## Context

- **Origin:** PRD v1.0 + legacy `PROJECT.md` (Project Atlas) + legacy `ROADMAP.md` (8 milestones, 10-week plan) archived at `.planning/legacy/`
- **Design specs:** `.planning/specs/` — SPEC-001 core architecture, SPEC-002 lead discovery engine, SPEC-003 sales/proposal system, SPEC-004 development pipeline (20-section format). These are canonical refs for research/planning.
- **Codebase state (as-built):** Python 3.11+ FastAPI skeleton — 5 implemented files (`backend/config.py`, `backend/database.py`, `backend/agents/{base,ceo,lead_hunter}.py`); empty scaffolding in `src/`, `frontend/`, `tests/`, `backend/{templates,tools,workflows}/`. SQLAlchemy 2.0 async used but undeclared in `pyproject.toml`. Agents call LLMs via raw httpx (OpenRouter/Groq/Gemini), NOT LangGraph yet. No app entry point, no migrations, no tests, no CI, no lockfile. See `.planning/codebase/CONCERNS.md`.
- **Pricing:** INR — Websites ₹10K/25K/50K (Starter/Business/Premium) + Enterprise custom; Automations ₹15K/40K/80K+ + ₹5K+/mo support; Chatbots ₹20K setup + ₹3–15K/mo; Custom AI systems ₹50K+
- **Business model:** one-time + recurring (hosting, monitoring, SEO, maintenance, AI credits, analytics, security, content); every project should carry recurring revenue
- **Compliance sensitivity:** crawler must respect robots.txt; outreach rate-limited and anti-spam compliant (CAN-SPAM, GDPR, India DPDP); approval gates required for contracts/payments; auditable AI decision log

## Constraints

- **Tech stack (declared):** Python 3.11+ / FastAPI / SQLAlchemy async / Supabase (PostgreSQL + pgvector) / Redis / httpx; frontend planned Next.js 14 + React 18 + Tailwind v4; AI via OpenRouter (free), Google AI Studio (free), Groq (free), Ollama (local) — no paid API keys assumed
- **Budget:** free/low-cost tiers wherever possible (per PRD AI section); deployment to free tiers of Vercel/Cloudflare/Netlify where feasible
- **Compliance:** platform terms + robots.txt + anti-spam law must be respected — this constrains scraping/outreach designs
- **Approval gates:** contracts, payment collection, and commitments outside pricing rules require explicit human approval
- **Timeline (legacy):** original 10-week/8-milestone plan; will be re-derived by roadmap
- **Dependency integrity:** `pyproject.toml` missing `sqlalchemy`; `langgraph>=0.0.30` pin is ancient; no lockfile — must fix during foundation phase

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| GSD workflow initialization (auto mode) | PRD comprehensive; existing skeleton + specs provide context | ✓ Good |
| Keep `.planning/specs/` as canonical refs | Specs define 20-section architecture; avoid re-deriving | ✓ Good |
| Archive legacy PROJECT.md/ROADMAP.md to `.planning/legacy/` | GSD versions supersede them; preserve prior thinking | ✓ Good |
| Standard granularity + parallel execution | Balanced phase size for large system; independent plans run in parallel | — Pending |
| Continue FastAPI/Python backend (not rewrite) | Existing skeleton aligns with PRD stack; salvage config/db/agents | ✓ Good |
| Agent calls via httpx (existing), LangGraph declared for orchestration | Works today; swap if orchestration needs grow | — Pending |

---

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state (users, feedback, metrics)

---
*Last updated: 2026-08-04 after initialization*
