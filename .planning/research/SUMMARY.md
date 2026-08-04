# Project Research Summary

**Project:** AI Agency OS
**Domain:** Autonomous AI-powered digital agency platform — multi-agent orchestration (discovery → sales → legal/finance → delivery → maintenance), web intelligence, outreach/negotiation, document generation, payments, owner dashboard
**Researched:** 2026-08-04
**Confidence:** MEDIUM-HIGH

## Executive Summary

AI Agency OS is a single-owner, autonomous agency platform that operates the full agency loop — lead discovery, website intelligence, AI sales and negotiation, proposals/contracts, payments, project delivery, and maintenance — with human approval only at defined gates (contracts, payments, commitments outside pricing rules). Research across all four dimensions converges on one coherent verdict: experts build this class of system as **durable per-deal state machines (LangGraph 1.x with Postgres checkpointing) for control flow, a Postgres outbox + asyncio worker for long I/O side effects, an append-only decision log for auditability, and a compliance layer (robots.txt, rate limits, suppression list, consent records) as the foundation — not an afterthought**. The declared FastAPI/Python/Supabase stack is the right family but every pin is 1–3 years stale and three dependency gaps are release-blockers (undeclared `sqlalchemy`, missing `alembic`, no lockfile). LangGraph 1.x is a complete API rewrite from the declared 0.0.x pin and must be treated as new adoption.

Recommended build: **seven phases** — (1) Foundation (package/dependency repair + compliance middleware + audit/scheduler/budget core), (2) Orchestration core (LangGraph skeleton + approval gate, proven end-to-end before any external risk), (3) Discovery (API-first crawling, 3–5 high-yield sources, website intelligence, scoring), (4) Sales (pricing engine, compliant email outreach, guardrailed negotiation, audit-integrated proposals), (5) Legal + Finance (approval-gated contracts, idempotent payments, MRR dashboard), (6) Delivery, (7) Maintenance + Growth. Key scope corrections from features research: ship 3–5 lead sources, not the spec'd 15+; use INP, not FID (FID was retired in March 2024); LinkedIn stays official-API-only; WhatsApp requires approved templates and explicit opt-in; DPDP compliance is designed into the foundation phase ahead of the May 2027 enforcement activation.

Key risks and mitigations: scraping bans/legal exposure (mitigate: API-first, logged-out-public-only, no CAPTCHA bypass — ever, per-source legal flags, robots.txt + token-bucket rate limits); cold-email deliverability collapse (SPF/DKIM/DMARC + separate outreach subdomain + 3–6 week warmup + verify-before-send gate + global suppression list, bounce <2–3%); negotiation agents conceding below floor or hallucinating promises (structured tool-call schemas, code-level floor validation — never prompt-only guardrails, escalation to owner); unbounded LLM cost (per-run/per-agent budgets with hard stops, exponential backoff, model tiering); prompt injection via scraped content (trust boundary at ingestion, sanitization, adversarial test fixtures); silent pipeline death (scheduler heartbeats + output-volume sink-hole detection); payment webhook replays (DB-level idempotency constraint + daily reconciliation); and DPDP exposure (consent-first — India has no "legitimate interest" for marketing; privacy notices + sourcing records built in from day one).

## Key Findings

### Recommended Stack

The declared stack family is correct (FastAPI + async SQLAlchemy/Supabase + Redis + httpx + LangGraph + Playwright + Next.js/Tailwind), but the version pins are 1–3 years stale, three critical gaps exist, and several declared choices are actively wrong (python-jose, passlib, Next 14/React 18, langgraph 0.0.x). Full detail: [STACK.md](STACK.md).

**Core technologies:**
- **LangGraph 1.2.x + langgraph-checkpoint-postgres 3.1.x**: agent orchestration — `interrupt()`/`Command(resume=...)` is the purpose-built human-approval gate; PostgresSaver gives durable suspend/resume. The declared `>=0.0.30` pin is a pre-1.0 API that won't port — adopt as new work
- **FastAPI 0.141 + uvicorn 0.52**: API gateway, webhooks, dashboard backend — current majors, right framework
- **SQLAlchemy 2.0.51 (`sqlalchemy[asyncio]`)** — CRITICAL: imported today, never declared; clean installs fail at import
- **Alembic 1.18**: migrations replace `create_all` (CONCERNS-mandated, CI-gated)
- **Supabase Postgres + pgvector**: primary store + embeddings; SQLAlchemy for queries, supabase client for auth/storage
- **Redis 8.1**: rate-limit counters, LLM cache, scheduler state. Never arq (hard-pins `redis<6`)
- **httpx 0.28 + tenacity 9.1**: LLM provider transport (OpenRouter/Groq/Gemini/Ollama) with retry/backoff — the 60s-no-retry path in CONCERNS is a real defect; fix in foundation
- **APScheduler 3.11 (`<4`)**: in-process cron; jobs only enqueue to outbox, never do work inline. 4.x is alpha
- **Playwright 1.62**: JS-rendered crawling, audit metrics, PDFs — document `playwright install chromium`
- **PyJWT 2.13 + pwdlib 0.3**: replace python-jose (deprecated, CVE history) and passlib (unmaintained, breaks with bcrypt≥4.1)
- **Next.js 16.3 + React 19.2 + Tailwind v4 + shadcn/ui**: owner dashboard — declared Next 14/React 18 is 2 majors behind
- **Stripe 15.4 / Razorpay 2.0**: bump in the finance phase; v7/v1.4 API surfaces are breaking-stale
- **Supporting**: tenacity, sentry-sdk (DSN configured, SDK undeclared), reppy (robots.txt), wappalyzer 2.0 (tech detection — MEDIUM confidence, keep regex fallback), slowapi or hand-rolled Redis limiter, num2words + Babel (INR legal invoice text), WeasyPrint 69 or Playwright PDF (pick one in docs phase), email-validator
- **uv + uv.lock** — CRITICAL: no lockfile exists; `>=`-only pins mean non-reproducible installs. First commit ships `.gitignore` + CI

**Package layout:** delete the empty `src/` scaffold; `backend/` is the single import root (installable, `__init__.py`, `packages.find`). `frontend/` stays a sibling (monorepo-lite, no workspace tooling).

### Expected Features

Benchmarked against GoHighLevel, HubSpot, AI SDRs (11x/Artisan), enrichment/sending stacks (Clay/Apollo/Instantly/Smartlead), audit tools, and agency reporting platforms. Full detail: [FEATURES.md](FEATURES.md).

**Must have (P1 — table stakes):**
- Compliance core (robots.txt, rate limits, shared suppression list, audit log) — underpins everything; PROJECT.md compliance sensitivity
- Lead collection from **3–5 high-yield compliant sources** (Google Places API, JustDial, web search, 1–2 directories) with dedup + source lineage — the spec's 15+ sources is a maintenance trap; source API churn is the #1 long-term risk
- Website intelligence: Lighthouse 4-category audit + Core Web Vitals (**INP, not FID** — FID retired March 2024), broken links, SSL, tech-stack detection, SEO checks — feeds scoring, proposals, opportunity detection
- Email discovery + verification with **send-time gate** (blocklist catch-all/role-based/unverified; bounce <2% target) — non-negotiable for deliverability and the DPDP sourcing story
- Weighted 7-factor lead scoring + tier classification (Hot/Warm/Cold/Raw)
- Opportunity detection with ROI estimates for 3–5 industries (the wedge: "you're losing ₹X/month")
- Email outreach sequences: personalization, follow-ups, unsubscribe + physical address + privacy notice in every message
- Reply classification + owner escalation on low confidence
- Proposal generator embedding audit scorecard + opportunities + pricing
- Pricing engine: deterministic floors, margins, negotiation limits (AI narrates, math decides)
- Contract generator from versioned lawyer-approved templates + **owner approval gate** + e-signature
- Payment collection (one-time, Stripe/Razorpay) + invoices
- Ops dashboard: pipeline kanban, approval center, activity/decision-log view

**Should have (differentiators):** ROI-quantified opportunity detection ("your restaurant loses ₹X/month without online booking") — unique vs. audit tools that score but don't monetize; guardrailed autonomous negotiation with escalation — no market competitor negotiates; the end-to-end loop through delivery + recurring revenue (the product thesis); DPDP-first compliance as a genuine India-market gap; audit report as a sales weapon (free-audit lead capture); auditable AI decision log + approval gates as the "trust brand" — 2026 market data shows fully-autonomous AI SDRs (Artisan, 11x) reverted to hybrid human-AI models; the credible version of "autonomous" asks permission and shows its work.

**Defer (v1.x → v2+):** WhatsApp channel (P2 — requires pre-approved templates, explicit opt-in flow, quality-rating monitoring; email first, WhatsApp for replies/opted-in nurture); recurring billing + maintenance plans (P2 — trigger: first delivered clients); full autonomous negotiation agent (P2 — launch in Sales phase as draft-and-escalate with the guardrail validation layer; expand after proposal-acceptance data exists); Cal.com meeting scheduling (P2); remaining discovery sources (P2); automated white-label client reports (P2); project/task generation from contracts (P2, own milestone per SPEC-004); data-freshness re-verification (P2); client health + upsell engine, voice AI, backlink analysis, inbound speed-to-lead, white-label SaaS resale (v2+ or explicitly out of scope per PROJECT.md).

**Anti-features (deliberately NOT built):** mass cold email to purchased/scraped lists (DPDP has NO legitimate-interest escape — penalties up to ₹250 crore); LinkedIn browser automation (ToS §8.2, hiQ contract liability, bans — official API only); WhatsApp bulk to non-opted-in numbers (template approval + tier bans); autonomous contract signing (owner approval is the trust floor); full autonomy with zero oversight; voice AI dialers (consent + recording law; India is WhatsApp-first); backlink analysis (paid APIs, low ROI); white-label SaaS resale (out of scope).

### Architecture Approach

Verdict: **control flow in graphs, side effects in queues, truth in Postgres.** LangGraph 1.x state machines own "what happens next" (one graph per deal, `thread_id` = pipeline_run_id, PostgresSaver checkpoints); a Postgres outbox table + in-process asyncio worker owns long I/O jobs (crawls, sends, renders) with `FOR UPDATE SKIP LOCKED` claiming and idempotent consumers; Postgres owns every persistent fact. Explicitly NOT: Temporal (infra weight at this scale), n8n (second runtime, no code-native HITL), message-bus control flow (un-debuggable), Kafka/Redis-bus-everything (SPEC-001 NFRs are aspirational; re-derive pragmatically for a free-tier single instance). Full detail: [ARCHITECTURE.md](ARCHITECTURE.md).

**Major components:**
1. **API Gateway** (FastAPI) — JWT auth, rate limits, approval responses, audit queries, payment webhooks; lifespan wires init_db + scheduler + worker
2. **CEO Supervisor Graph** — daily plan from budgets, KPI review, escalation, replan-on-failure
3. **Pipeline State Machines** (LangGraph per deal) — discovery → sales → legal → finance → delivery → maintenance; nodes = department agents; `interrupt()` at gates
4. **Approval Engine** — `approval_requests` table (context, expiry, status) + APScheduler sweeper for timeout/escalation; dashboard queries the table, API resumes graphs via `Command(resume=...)`
5. **Outbox queue + asyncio worker** — same-transaction inserts guarantee no lost jobs; scheduler enqueues only
6. **Crawler Service** — layered: robots policy (deny-by-default) → per-domain token bucket with jitter → httpx fetch → Playwright escalation for JS-only; Crawlee as documented fallback if breadth grows
7. **Decision Log** — append-only `decision_events` table written through a single AuditService (correlation_id, PII redaction at write, export endpoint)
8. **Repositories + Models** — typed DB access; wire the mock-data agents to real tables
9. **Next.js dashboard** — approvals queue, pipeline funnel, decision explorer, config

Key patterns to follow: `interrupt()`/`Command(resume=...)` approval gates with a small policy table (action_type → requires_human) — config-driven gates via a generic engine are over-engineering; transactional outbox with idempotent consumers; typed task protocol replacing the current keyword-string dispatch (`"discover" in task.lower()` anti-pattern); scheduler/worker separation from day one; webhooks land → enqueue → reconcile, never inline work.

### Critical Pitfalls

Top pitfalls and prevention strategies. Full detail: [PITFALLS.md](PITFALLS.md).

1. **Scraping without anti-detection planning → IP bans, captchas, dead pipeline** (Google Maps hardened: TLS fingerprinting, rotating classes, SearchGuard) — prefer official APIs (Places API); per-domain/IP limits with jitter; captcha = backoff signal, never a bypass; per-source health monitoring (SPEC-002 §18 conditions; enforcement code doesn't exist yet)
2. **Legal exposure from scraping** (hiQ $500K contract judgment, CNIL KASPR €200K fine, DMCA §1201 exposure for CAPTCHA bypass, Reddit v. Anthropic pending) — logged-out public data only; no fake accounts; no bypassing access controls; per-source "contact legality" flag gating outreach; treat scraped emails/phones as personal data
3. **DOM rot / data quality decay → silent stale leads** — measure parse-success rate per source per run (a 200 with 0 records is a failure); version selectors/schemas; validate every field before it becomes "sales-ready"
4. **Missing deliverability infrastructure → outreach never reaches inbox** (SPF 10-lookup trap, DMARC missing, no warmup) — SPF/DKIM/DMARC on a separate outreach subdomain; 3–6 week warmup (start DNS early — warmup is calendar-time); verify-before-send; bounce <2–3%, complaints <0.3% (Google threshold)
5. **Automated outreach at scale → spam-trap hits and enforcement** (FTC $53,088/email since Jan 2025; CAN-SPAM applies to all commercial email) — caps enforced in code (`daily_outreach_limit=25` is a feature: low volume = compliance asset), unsubscribe + physical address in every send, global suppression list consulted on every send
6. **Treating India/DPDP as "no GDPR"** — no legitimate-interest basis for marketing (Section 7 numerus clausus); consent-first, notices in English + Hindi; penalties up to ₹250 crore; **DPDP Rules 2025 active May 13, 2027 — ship before it, bake the machinery in now** (consent records, erasure, breach runbook)
7. **Negotiation agent concedes below floor / hallucinates promises** (Air Canada chatbot liability is the canonical warning) — all commitment-relevant facts are structured tool calls validated against the pricing DB; code-level floor enforcement (prompt text alone is never sufficient); below-floor routes to approval gate; contracts fill ONLY from the validated commitment record, never from parsing the transcript
8. **Indirect prompt injection via scraped content** (OWASP LLM01; AutoJack June 2026; poisoned search results) — this product's core data is web content: trust boundary at ingestion (content never shares context with instructions), sanitize HTML comments/scripts, adversarial fixtures in tests, action-validation gate on content-derived actions
9. **Unbounded LLM cost** ($47K retry-loop incident, $6,531 weekend) — per-agent/per-run budgets with hard stops, backoff with max attempts, context trimming, model tiering (cheap for classify, expensive only for negotiation)
10. **Silent scheduled-pipeline failures** — "last successful run" heartbeat per pipeline with staleness alerts; structured job status; **sink-hole detection** (discovery produced 0 leads 3 days running is an incident)
11. **No audit trail for AI decisions** — append-only decision log from foundation phase; retrofitting is expensive; regulators hold the human operator liable, "the model did it" is not a defense
12. **Payment webhook non-idempotency** (Stripe retries up to 72h; TanStack double-credit postmortem) — DB unique constraint on (event_id, event_type) with effects in the same transaction; daily reconciliation vs provider balance; replay test in acceptance criteria
13. **AI audit scores as sales truth** — lab vs. field data labeled (CrUX needs 1k–10k pageviews, ~28-day lag); fixture-validated detectors (≥90%); findings-first reports with confidence annotations; a wrong confident score poisons the sales demo

## Implications for Roadmap

Integrating the architecture build-order verdict (foundation → orchestration core → discovery → sales → legal/finance → delivery → maintenance/growth) with features research scope corrections, stack research, and pitfalls research. Standard granularity: 7 phases.

### Phase 1: Foundation — Repairs + Compliance Core + Agent Runtime Core
**Rationale:** Blocks everything; zero external risk; the compliance middleware must exist before ANY fetch or send path is written (pitfalls research: "never ship a scraper before the compliance box"; CONCERNS: no entry point/migrations/repositories, dual source roots). DPDP machinery and audit log are foundation deliverables, not retrofit.
**Delivers:** package layout fix (delete `src/`, `backend/` installable, README); `uv` + `uv.lock`; dependency repair (declare `sqlalchemy[asyncio]>=2.0.51`, add alembic, tenacity, sentry-sdk, email-validator; bump fastapi/uvicorn/pydantic/redis/httpx; swap python-jose→PyJWT, passlib→pwdlib); Alembic migration baseline replacing `create_all`; FastAPI entry + lifespan (init_db, scheduler, worker); repositories; new tables (`approval_requests`, `outbox_events`, `decision_events`, `pipeline_runs`) + consent/source-lineage fields on leads; JWT auth; **compliance middleware** (rate limiting, robots.txt util, suppression list, anti-spam send-gate skeleton); **agent core hardening** (per-run/per-agent spend budgets, retry/backoff via tenacity, model tiering, Gemini key to header); **AuditService** + decision-log write path; scheduler activation with tests; CI (lint → typecheck → test → migrations check) + `.gitignore`.
**Addresses:** FEATURES compliance core; FEATURES consent/suppression/audit-log items; STACK gaps 1–10; ARCHITECTURE build-order step 1.
**Avoids:** Pitfalls 9, 10, 11 (budgets, scheduler heartbeats, audit trail from day 1); Pitfalls 2, 5, 6 (compliance before any external interaction); CONCERNS dependency/entry-point failures.

### Phase 2: Orchestration Core — LangGraph + Approval Gate
**Rationale:** The approval-gate suspend/resume loop is the product's trust mechanism and must be proven end-to-end before crawling (phase 3) or money (phase 5). Built once, reused by every department. Pure infrastructure, no external risk.
**Delivers:** LangGraph 1.2 adoption as new work (unpin 0.0.x, pin `>=1.2`); typed task protocol replacing keyword dispatch; one generic pipeline state machine with PostgresSaver (`thread_id` = pipeline_run_id); **Approval Engine** (`approval_requests` + API endpoints + sweeper for timeout/escalation via `Command(resume=...)`); APScheduler + outbox worker (scheduler enqueues, worker drains); CEO supervisor graph skeleton; decision-log wiring through all nodes; first working approve/reject round-trip with the existing CEO/LeadHunter agents.
**Uses:** LangGraph 1.2.10, langgraph-checkpoint-postgres 3.1, Postgres outbox, APScheduler 3.11.
**Avoids:** Anti-patterns 1–3 (keyword dispatch, message-bus control flow, bare boolean approval); Pitfall 11 (audit from first node run).

### Phase 3: Discovery — Crawler, Sources, Intelligence, Scoring
**Rationale:** First value delivered; compliance gates from P1 make crawling legally defensible. The crawler is on the critical path to sales (scoring's Automation/AI factors and proposals need crawl output). Features scope correction: 3–5 high-yield sources, not 15+.
**Delivers:** layered crawler service (robots deny-by-default → per-domain token bucket → httpx → Playwright escalation); source registry with per-source legal flags, health, versioned adapters; 3–5 sources (Google Places API-first, JustDial, web search, 1–2 directories); dedup + lineage; email discovery + verification pipeline (catch-all/role-based flagged); weighted scoring + tier classification; website intelligence (Lighthouse 4 categories + INP-based CWV, broken links, SSL, tech stack via wappalyzer + regex fallback, SEO checks); opportunity detection + ROI for 3–5 industries; parse-success metrics + ingestion sanitization (prompt-injection boundary).
**Addresses:** FEATURES P1 discovery/intelligence/scoring items; SPEC-002 (with corrections: INP not FID, source count).
**Avoids:** Pitfalls 1, 2, 3, 8, 13 (bans, legal exposure, DOM rot, injection, audit-score honesty).
**Research flags:** HIGH — Google Maps anti-bot feasibility spike (stealth browser viability post-2024 hardening; assume API-first posture); Places API free-tier limits (20 results/Nearby Search, 30-day storage restriction); JustDial/IndiaMART anti-bot behavior (LOW confidence — vendor docs only); verification provider choice on free tiers; wappalyzer maintenance verification.

### Phase 4: Sales — Pricing, Outreach, Negotiation Guardrails, Proposals
**Rationale:** Money-adjacent logic; the approval mechanism is exercised (P2) before real sends. Deliverability infrastructure must land WITH outreach, not after (warmup is a calendar-time investment — DNS/warmup seeds can start in P1/P3). Negotiation guardrails require the pricing engine first (negotiation without floors is an LLM chatting about money = liability).
**Delivers:** pricing engine (deterministic hours×complexity×market×ROI → price bounds, min-price floor, margin); email outreach sequences (personalization, follow-ups, unsubscribe + physical address + privacy notice; caps enforced in code); **deliverability infra** (SPF/DKIM/DMARC on outreach subdomain, warmup schedule, verify-before-send gate, bounce/complaint monitoring); reply classification + owner escalation; proposal generator embedding audit scorecard + opportunities + pricing; **negotiation agent in draft-and-escalate mode** (tool-call schema validation against pricing DB, code-level floor enforcement, below-floor → approval gate, transcript-vs-commitment reconciliation; full autonomy deferred to v1.x after acceptance data exists); first real contract-approval gate wired.
**Addresses:** FEATURES P1 sales items; pricing/negotiation guardrails (FEATURES P2 negotiation is delivered as the validation layer now, autonomous mode later).
**Avoids:** Pitfalls 4, 5, 6, 7, 8 (deliverability, anti-spam, DPDP consent gating, negotiation floors, injection fixtures as acceptance criteria).
**Research flags:** HIGH — deliverability provider choice (SendGrid free tier vs SES/Resend vs SMTP fallback), warmup tooling; verification API free tiers at send-time volume; negotiation validation patterns.

### Phase 5: Legal + Finance — Contracts, Payments, Finance Dashboard
**Rationale:** Gates built in P2 get their first financial teeth. Contract execution gates project creation (don't build delivery before legal/finance). Webhook idempotency is a known incident class — put it in acceptance criteria. Stripe/Razorpay bumps land here (STACK: don't write new code against v7/v1.4).
**Delivers:** contract/SOW/NDA generation from versioned lawyer-approved templates (Jinja2) with jurisdiction variants (India/International); **owner approval gate** before any contract send (reuses P2 Approval Engine); e-signature integration (SignWell/HelloSign — swappable); payment collection (Stripe 15.4 + Razorpay 2.0 bump) + invoices (INR amount-in-words via num2words, Babel formatting) + payment reminders; **webhook idempotency** (DB unique constraint on event_id, effects from event log, replay test) + **daily reconciliation job**; finance dashboard v1 (pipeline value, MRR from billing engine — never manual entry, margins); decision-log export endpoint.
**Addresses:** FEATURES proposals/contracts/payments items; FEATURES finance-dashboard P1-lite; STACK finance bumps.
**Avoids:** Pitfall 12 (webhook replay/double-credit — acceptance-criteria item); Pitfall 2's legal boundary (no autonomous contract execution); stale-major integration debt.
**Research flags:** HIGH — Stripe 15.x / Razorpay 2.x current API surfaces and free-tier pricing; e-sign provider choice; India GST/invoice requirements; WeasyPrint-vs-Playwright-PDF decision (pick one, per STACK).

### Phase 6: Delivery — Project Management + Dev Pipeline
**Rationale:** Consumes executed contracts + payment schedules (dependency: don't build delivery before legal/finance). This is SPEC-004's milestone; maintenance (P7) requires deployed client projects to monitor.
**Delivers:** project creation from executed contract; task generation; PM/QA agents (typed LangGraph nodes with budgets — no stub agents pass acceptance); deploy automation (Vercel/Cloudflare/Netlify/Railway/VPS) with auto-config (analytics, forms, monitoring, SEO); go-live approval gate only when outside pricing rules.
**Addresses:** FEATURES project/task generation (P2, own milestone per SPEC-004); PROJECT.md development pipeline + QA department.
**Avoids:** Pitfall 9 (budgets on dev agents — "no stub passes acceptance" debt pattern); anti-pattern 5 (heavy work in scheduler/BackgroundTasks — all via outbox).
**Research flags:** MEDIUM — deploy-provider free-tier APIs (Vercel/Cloudflare/Netlify current limits); n8n vs in-house automation for client-delivery glue (features research recommends n8n self-hosted; decide here).

### Phase 7: Maintenance + Growth — Monitoring, Reports, Recurring Revenue
**Rationale:** Long tail — client reports are the monitoring output, monitoring requires deployed clients, and recurring revenue closes the product thesis loop. WhatsApp needs proven email engagement first.
**Delivers:** monthly maintenance checks (SSL, uptime, broken links, SEO, security, deps) sharing the P3 crawler engine at different cadence; automated white-label client reports (scheduled, branded); recurring billing + maintenance plans (Stripe Billing) feeding the finance dashboard; client health scoring + upsell triggers (v2 features once telemetry exists); WhatsApp channel (approved utility/auth templates first, opt-in collection during conversations, quality-rating monitoring — never cold marketing blasts); scheduler heartbeats on every maintenance cycle.
**Addresses:** FEATURES P2 items (WhatsApp, recurring billing, client reports); FEATURES v2+ health/upsell start.
**Avoids:** Pitfall 10 (silent maintenance-pipeline death — heartbeat + sink-hole alerting); Pitfall 13 (reports labeled lab vs field); FEATURES WhatsApp anti-pattern (no bulk to non-opted-in numbers).
**Research flags:** MEDIUM — WhatsApp Business API template approval flow + quality-rating mechanics (Infobip docs, Meta rules); recurring-billing setup (Stripe Billing free tier).

### Phase Ordering Rationale

- **Dependency-driven:** foundation → orchestration → discovery → sales → legal/finance → delivery → maintenance follows the FEATURES dependency graph (verification gate requires enrichment; scoring requires crawler; negotiation requires pricing engine; contract execution gates project creation; reports require monitoring which requires delivery) and ARCHITECTURE's build order (approval gate built once in P2, reused not re-invented).
- **Risk-sequenced:** phases 1–2 are pure infrastructure with zero external risk; phase 3 introduces the only legally-sensitive external interaction (crawling) while the system is cheap to fail, behind the P1 compliance middleware; phases 4–5 put money in motion only after the approval mechanism has been exercised; phases 6–7 consume everything prior.
- **Compliance-first:** DPDP consent machinery, suppression list, audit log, and rate-limit middleware are P1 deliverables because every later phase inherits them; retrofitting is expensive and enforcement activates May 2027.
- **Scope corrections embedded:** 3–5 sources (not 15+), INP (not FID), LinkedIn official-API-only, WhatsApp template-gated, negotiation launches guardrail-first.

### Research Flags

Phases likely needing deeper research during planning (`/gsd-plan-phase --research-phase <N>`):
- **Phase 3 (Discovery):** Google Maps anti-bot feasibility spike; Google Places API free-tier limits; JustDial/IndiaMART scraping behavior (LOW confidence sources); email verification provider choice on free tiers; wappalyzer maintenance status
- **Phase 4 (Sales):** deliverability infrastructure (sending provider, warmup tooling, SPF/DMARC mechanics at free tier); verification API send-time costs
- **Phase 5 (Legal + Finance):** Stripe 15.x / Razorpay 2.x current API surfaces (breaking changes from declared pins); e-sign provider free tiers; India GST/invoicing specifics; DPDP legal review of the lawful-basis approach with counsel
- **Phase 7 (Maintenance + Growth):** WhatsApp Business API template approval + quality rating; recurring billing configuration
- **Phase 6 (Delivery):** deploy provider free-tier APIs; n8n adoption decision

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** FastAPI + SQLAlchemy + Alembic + uv are commodity, well-documented territory; CONCERNS.md/codebase maps already enumerate the defects to fix
- **Phase 2 (Orchestration core):** LangGraph interrupts/checkpointing verified against official docs (HIGH confidence sources); pattern examples exist in ARCHITECTURE.md

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI/npm registries 2026-08-04; official LangGraph docs for interrupt/checkpoint APIs. Qualitative ecosystem-fit claims (pydantic-ai/CrewAI, wappalyzer maintenance) MEDIUM |
| Features | MEDIUM | Ecosystem feature sets well-documented; market-behavior claims (hybrid > autonomous AI SDRs, LinkedIn ban patterns) from secondary sources; legal analysis is general guidance, not legal advice |
| Architecture | HIGH | Orchestration/approval-gate/outbox patterns verified against official docs + established literature (microservices.io); scheduler/crawler component choices are MEDIUM (ecosystem consensus) |
| Pitfalls | MEDIUM-HIGH | Documented incidents (FTC, Stripe retries, injection attacks) HIGH; India-specific anti-bot behavior LOW; DPDP legal interpretation MEDIUM (statutory text supports it; counsel review recommended) |

**Overall confidence:** MEDIUM-HIGH — the technology and architecture recommendations are well-supported; the compliance and source-viability areas carry the most uncertainty and are flagged for phase-level research.

### Gaps to Address

- **Google Maps scraping viability post-2024 hardening:** LOW confidence — assume the strictest posture (Places API-first) and run a feasibility spike in Phase 3 planning
- **JustDial/IndiaMART anti-bot behavior and data freshness:** LOW confidence (vendor docs only) — spike with real sources in Phase 3; commercial data vendors (e.g., datagators) as documented fallback
- **DPDP lawful-basis interpretation** (no legitimate interest for marketing): MEDIUM — consult counsel before relying on any specific sourcing/lawful-basis choice; design consent-first regardless
- **Email verification + deliverability providers on free tiers:** unresolved — research in Phase 4 planning; the <2% bounce target is the acceptance bar
- **Stripe 15.x / Razorpay 2.x API surfaces:** unresolved — verify at Phase 5 planning, not at implementation time
- **SPEC-001 aspirational NFRs** (10k msg/s, 99.9% k8s): mismatch with free-tier reality — re-derive pragmatically (Postgres-first; escalate infra only at documented 10x/100x thresholds); document the deviation from SPEC-001's Redis bus
- **WeasyPrint vs Playwright PDF:** undecided — pick one in Phase 5 (docs phase); don't add both
- **n8n role** (features research suggests it for delivery glue; architecture says "optional automations"): decide in Phase 6 planning
- **Wappalyzer maintenance:** MEDIUM confidence — keep regex fallback; verify at adoption in Phase 3

## Sources

### Primary (HIGH confidence)
- PyPI JSON API (`pypi.org/pypi/<pkg>/json`) and npm registry — all stack versions verified 2026-08-04
- LangGraph official docs — `interrupt()`/`Command(resume=...)` human-in-the-loop semantics, `PostgresSaver` persistence
- microservices.io transactional-outbox pattern + `FOR UPDATE SKIP LOCKED` operational guidance
- PyPA packaging docs — src vs flat layout; PyPA recommendation for app-style projects
- Crawlee (Apify) official docs — `respect_robots_txt_file`, adaptive crawling
- web.dev / Chrome docs — Lighthouse performance scoring weights, INP replacement of FID, lab-vs-field CrUX data
- Stripe webhook retry docs (72h backoff); Gmail/Yahoo bulk-sender requirements (SPF/DKIM/DMARC, 0.30% complaint threshold)
- Court records/press releases: hiQ v. LinkedIn, Meta v. Bright Data, CNIL KASPR fine, FTC CAN-SPAM penalties, DPDP Act 2023 + DPDP Rules 2025 (notified 2025-11-13, active 2027-05-13)
- OWASP LLM Top 10 (LLM01); security postmortems (AutoJack, poisoned search results, $47K retry-loop, TanStack double-credit)
- `.planning/codebase/` (STACK.md, INTEGRATIONS.md, CONCERNS.md, STRUCTURE.md) — as-built ground truth

### Secondary (MEDIUM confidence)
- AI SDR market analyses (Miniloop, Instantly, SaaS Hackers) — hybrid human-AI > fully autonomous; data provenance demands
- Apollo.io SLA benchmarks — bounce tiers, freshness 30–90 days, seed-test protocol
- Infobip/Meta WhatsApp template compliance docs — template approval, quality ratings, tier limits
- DPDP marketing-compliance analyses (leadzen.ai, TeamBench, dakshraj.com) — Section 7 numerus clausus, no legitimate-interest equivalent
- LangGraph vs Temporal comparisons; APScheduler vs Celery consensus; FastAPI BackgroundTasks limitations
- SaaS finance metric definitions and benchmarks (LTV:CAC 3:1 floor, CAC payback <12mo healthy, NRR >100%)
- AI negotiating-agent research (Schneider et al., arXiv:2404.04289); Air Canada chatbot ruling

### Tertiary (LOW confidence)
- Google Maps anti-bot specifics (TLS fingerprinting, rotating class names, SearchGuard) — community reports; shifts quarterly, re-verify in Phase 3
- JustDial/IndiaMART scraping behavior and commercial vendor data-freshness claims — vendor documentation
- wappalyzer detection accuracy and maintenance status — vendor claims
- Qualitative ecosystem-fit claims (pydantic-ai/CrewAI/OpenAI Agents SDK capabilities, Lighthouse Python wrapper state)

---
*Research completed: 2026-08-04*
*Ready for roadmap: yes*
