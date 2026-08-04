# Architecture Research

**Domain:** Autonomous AI-powered digital agency platform (15+ specialized AI agents/departments, long-running async pipelines, human approval gates)
**Researched:** 2026-08-04
**Confidence:** HIGH (orchestration, approval gates, packaging — verified against official docs); MEDIUM (scheduler, crawler component choices — ecosystem consensus, multiple credible sources)

## Verdicts (TL;DR)

| Question | Verdict |
|----------|---------|
| **Orchestration pattern** | **LangGraph state machines** for pipeline control flow (native `interrupt()` = approval gates, `PostgresSaver` = durable suspend/resume). Postgres outbox table + in-process asyncio worker for async *side-effect jobs* (crawls, outreach sends, reports). NOT Temporal (infra weight), NOT n8n (second runtime, no code-native HITL), NOT pure message-bus (control flow in queues is un-debuggable) |
| **Approval gate** | **LangGraph `interrupt()` + `Command(resume=...)`** — graph suspends at a checkpoint, `approval_requests` table is the human-facing pending state, APScheduler sweeper handles timeout/escalation, every decision appended to `decision_events` |
| **Scheduler** | **APScheduler `AsyncIOScheduler` in-process** — its jobs only *enqueue* work into the outbox, never do heavy work inline; sweeper jobs for approval expiry + stuck-job recovery. Cron for MVP only; Celery: no |
| **Crawler** | Layered: httpx fetch + `urllib.robotparser` + per-domain token-bucket rate limiter, **escalate to Playwright only for JS-rendered sites**. Crawlee (Apache-2.0) is the validated turnkey alternative (`respect_robots_txt_file=True`) |
| **Package layout** | **Flat layout, `backend/` as the single importable package — delete `src/`.** Add `__init__.py` files, make project installable (`pip install -e .`, explicit `packages.find`). `frontend/` stays a sibling (monorepo-lite; no workspace tooling) |
| **Decision log** | **Append-only `decision_events` DB table = system of record** (queryable, exportable, 7-yr retention). Optional Postgres `LISTEN/NOTIFY` or Redis pub/sub *only* for live dashboard updates. No separate event store (Kafka/EventStore) |

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        OWNER DASHBOARD / ADMIN UI (Next.js)               │
│        approvals │ pipeline funnel │ decision explorer │ config          │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ HTTPS (JWT)
┌───────────────────────────────▼──────────────────────────────────────────┐
│                       API GATEWAY — FastAPI (backend/main.py)             │
│            auth │ rate limit │ routers: approvals, pipeline, audit,       │
│            leads, projects, payments-webhooks                            │
└───────┬───────────────────────────────┬───────────────────────────────────┘
        │ HTTP calls                    │ resume/approve responses
┌───────▼───────────────────────────────▼───────────────────────────────────┐
│                 ORCHESTRATION LAYER (LangGraph 1.x)                        │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  CEO Supervisor Graph (daily plan, escalations, KPI review)      │     │
│  └───────────┬──────────────────────────────────────────────────────┘     │
│  ┌───────────▼──────────────────────────────────────────────────────┐     │
│  │  Pipeline State Machines (one graph per deal/pipeline instance)  │     │
│  │  discovery → sales → legal → finance → delivery → maintenance    │     │
│  │  nodes = department agents · interrupt() = approval gates        │     │
│  │  checkpointer = PostgresSaver (thread_id = pipeline_run_id)      │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  APPROVAL ENGINE: approval_requests (DB) · sweeper (APScheduler) │     │
│  └──────────────────────────────────────────────────────────────────┘     │
└───────┬───────────────────────────────────────────────┬───────────────────┘
        │ enqueue jobs (outbox)                          │ write decisions
┌───────▼──────────────────────┐              ┌──────────▼──────────────────┐
│  JOB/QUEUE LAYER              │              │  DATA LAYER (Supabase/PG)   │
│  outbox_events table          │              │  businesses audits          │
│  └─ asyncio worker (in-proc)  │  ─────────► │  proposals contracts        │
│     └─ crawler worker         │              │  projects tasks             │
│     └─ outreach sender        │              │  approval_requests          │
│     └─ report renderer        │              │  outbox_events              │
│  APScheduler (daily runs,     │              │  decision_events (append-   │
│  sweeps)                      │              │   only, immutable)          │
└───────────────┬───────────────┘              └─────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────────────┐
│  EXTERNAL INTEGRATIONS: OpenRouter/Groq/Gemini (LLM) · Playwright (crawl) │
│  Google Places/directories (leads) · SendGrid (email) · Razorpay/Stripe   │
│  (payments) · Vercel/Railway/etc (deploy)                                 │
└───────────────────────────────────────────────────────────────────────────┘
```

**Design principle: control flow in graphs, side effects in queues, truth in Postgres.** LangGraph state machines own *what happens next* (including suspending for humans); the outbox queue owns *long I/O jobs* (crawls, emails, checks); Postgres owns every persistent fact (business state, approvals, decisions, outbox). This keeps the system debuggable (one graph per deal), auditable (append-only decision log), and resumable (checkpoints) without a distributed-systems platform.

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| API Gateway | Auth (JWT), rate limiting, HTTP surface for dashboard: approvals list/respond, pipeline status, audit queries, payment webhooks, admin config | FastAPI routers in `backend/api/`; lifespan wires `init_db()` + scheduler + worker |
| CEO Supervisor Graph | Daily plan from settings (lead budget, outreach budget), strategy, KPI review, escalation handling, replan on failure | LangGraph graph; nodes delegate to department subgraphs |
| Pipeline State Machines | One graph per deal: discovery → sales → legal → finance → delivery → maintenance; holds deal state; suspends at approval gates | LangGraph `StateGraph` with `TypedDict` state; `PostgresSaver` checkpointer; `thread_id` = pipeline_run_id |
| Department Agents (15+) | Domain reasoning: scanner, auditor, scorer, outreach, proposal, pricing, negotiation, contracts, finance, PM, dev, QA, maintenance, upsell | LangGraph nodes wrapping the existing `BaseAgent` hierarchy (replacing keyword dispatch with typed tasks); structured I/O via Pydantic |
| Approval Engine | Pending-approval registry (create, respond, expire), escalation policy, drives `Command(resume=...)` into graphs | `approval_requests` table + service; APScheduler sweeper for `expires_at` timeouts |
| Job Queue (outbox) | Durable at-least-once dispatch of heavy I/O jobs: crawl audits, enrichment batches, outreach sends, report renders; retries + DLQ | `outbox_events` table (status, attempts, next_run_at) + asyncio worker polling with `FOR UPDATE SKIP LOCKED` |
| Scheduler | Daily pipeline trigger, periodic sweeps (approval expiry, stuck jobs, maintenance checks, upsell health) | APScheduler `AsyncIOScheduler` started in FastAPI lifespan |
| Crawler Service | robots.txt policy, per-domain rate limiting, fetch/render, page metrics (perf/SEO/a11y), tech-stack detection | httpx + `urllib.robotparser` + asyncio semaphore/token bucket; Playwright escalation for JS-heavy sites |
| Decision Log | Immutable record of every AI decision: agent, action, inputs, outputs, rationale, confidence, correlation_id, human_reviewed | Append-only `decision_events` table; write through an `AuditService` used by all agents/nodes |
| Repositories | Typed DB access per entity; wire agents to real data (today agents return mock data) | `backend/repositories/`; SQLAlchemy async sessions from `database.py` |
| Settings/Config | Existing `Settings` (pydantic-settings); add: approval timeout, crawler concurrency, queue retry policy, decision-log retention | `backend/config.py` — extend, don't split |
| Frontend | Owner dashboard: approval queue, pipeline funnel, decision explorer, config panels | Next.js in `frontend/` |

## Recommended Project Structure

```
ai-agency-os/
├── pyproject.toml            # fix: add README.md (build fails without it), packages.find, real pins
├── backend/                  # THE single Python package (delete src/)
│   ├── __init__.py           # ← missing today; required
│   ├── main.py               # FastAPI app + lifespan (init_db, scheduler, worker) — MISSING today
│   ├── config.py             # Settings (exists — extend)
│   ├── database.py           # engine/session/models (exists — split models out later)
│   ├── models/               # ORM models per entity (Alembic-managed)
│   ├── repositories/         # typed DB access
│   ├── agents/               # existing BaseAgent hierarchy → LangGraph node adapters
│   │   ├── base.py           # keep BaseAgent as the LLM-call core; add typed task protocol
│   │   ├── ceo.py, lead_hunter.py, sales.py, ...   # one file per department
│   ├── workflows/            # LangGraph graphs (pipeline graphs + CEO supervisor)
│   ├── services/             # crawler, outbox, approvals, pricing, audit, templates
│   ├── api/                  # FastAPI routers (auth, approvals, audit, pipeline, webhooks)
│   ├── tools/                # shared tools (robots.py, rate_limit.py, fetch.py)
│   ├── templates/            # Jinja2 (contracts/emails/proposals — exists, empty)
│   └── worker.py             # asyncio outbox worker entry
├── frontend/                 # Next.js dashboard (sibling, no workspace tooling)
├── tests/                    # mirrors backend/
├── automations/              # optional n8n scripts for peripheral glue (CRM sync, report emails)
├── config/  deploy/  scripts/  docs/
└── .planning/
```

### Structure Rationale

- **`backend/` is the one import root. Delete `src/`.** The repo today has two competing source roots (`src/` empty scaffold + `backend/` with all 5 real files) — this is the #1 placement-ambiguity risk flagged in `.planning/codebase/CONCERNS.md` and `STRUCTURE.md`. All implemented code uses `from backend.config import ...` imports; keep the name, kill the duplicate. (Full src-vs-flat analysis in Patterns section.)
- **`workflows/` next to `agents/`**: LangGraph graphs compose the existing agent classes; they are siblings in the same package. This is already the declared intent of the empty `backend/workflows/` dir.
- **`services/` not `src/services/`**: domain services (outbox, approvals, crawler, pricing) belong inside the package. The `src/services` scaffold dies with `src/`.
- **One package, not a monorepo**: Python backend + Next.js frontend + optional automations scripts is monorepo-*lite*; no npm/yarn workspace orchestration, no shared build tooling. Introduce workspace tooling only if frontend and backend ever share code (they don't).
- **`models/` split from `database.py`**: today all 9 models + enums live in one 308-line file. Split per-entity when Alembic migrations land (phase 1), so migration autogeneration works cleanly.

## Architectural Patterns

### Pattern 1: Pipeline State Machine per Deal (LangGraph + PostgresSaver)

**What:** Each business opportunity runs through one LangGraph state machine (`thread_id` = pipeline run ID). Nodes are department agents; edges are deterministic guards (scoring threshold, guardrail checks); state is the deal's typed state (business_id, proposal, price, statuses). Compiled with `PostgresSaver` so every node transition is checkpointed to Postgres.

**When to use:** Any multi-step business flow with deterministic gates + LLM reasoning + pauses — i.e., every department pipeline here. This is the pattern LangGraph's own docs promote for long-running, stateful agents (verified: `langgraph.checkpoint.postgres.PostgresSaver`; docs recommend it over `MemorySaver` which "does not persist between restarts").

**Trade-offs:** Requires migrating agent code from free-form `execute(task)` string dispatch to typed nodes (one-time cost); debugging graphs needs LangGraph Studio or careful state schemas; version upgrades between LangGraph 0.0.x pin and 1.x are breaking (current pin `>=0.0.30` is ancient — unpin and pin current stable at the orchestration phase).

**Example (conceptual — matches official interrupt docs):**
```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.postgres import PostgresSaver

class DealState(TypedDict):
    business_id: str
    proposal: dict
    price: float
    approved: bool

def proposal_node(state: DealState) -> dict:
    proposal = proposal_agent.build(state["business_id"])   # typed agent call
    needs_human = proposal.price > settings.auto_approve_threshold
    if needs_human:
        decision = interrupt({"action": "approve_contract",
                              "proposal": proposal})        # SUSPEND here
        return {"proposal": proposal, "approved": decision.get("approved")}
    return {"proposal": proposal, "approved": True}

# API side (owner clicks Approve):
graph.update_state(config, {"approved": True}, as_node="proposal_node")
# or resume: graph.stream(Command(resume={"approved": True}), config)
```

### Pattern 2: Approval Gate — interrupt + approval_requests + sweeper

**What:** Three coordinated pieces:
1. **Suspension:** the graph calls `interrupt(payload)` at any gate (contract, payment, discount > cap, unsupported commitment). LangGraph persists the checkpoint and returns; the thread waits indefinitely. Verified against official LangGraph docs (`interrupt` + `Command(resume=...)`; "The graph will wait indefinitely until resumed").
2. **Human-facing state:** the interrupt node ALSO writes an `approval_requests` row (id, action_type, context, expires_at, status PENDING/APPROVED/REJECTED/EXPIRED). The dashboard queries this table — never LangGraph internals. Owner response → API resolves the row → service resumes the graph via `Command(resume=...)` (LangGraph 1.x) or `graph.update_state(...)`.
3. **Timeout/escalation:** an APScheduler sweeper (every 5 min) marks rows past `expires_at` as EXPIRED and resumes the graph with `{"approved": False, "reason": "timeout"}` so the graph takes the escalation branch (CEO escalation or hold). Satisfies SPEC-001 FR-015 ("approval timeout with escalation") and FR-016 (partial approval with modifications — resume payload can carry edited values).

**When to use:** Every gate listed in PROJECT.md constraints: contracts, payment collection, commitments outside pricing rules. This replaces the current dead `Proposal.human_approval_required` boolean (a column with no logic — flagged in CONCERNS.md).

**Trade-offs:** interrupt-based gates are code-positioned (a gate exists where an `interrupt()` call is) — config-driven gates per action type (SPEC-001 FR-013) need a small policy table mapping action_type → requires_human, evaluated in the node before interrupting. That's the right compromise; a generic "workflow engine" config for gates is over-engineering at this scale.

**Example:**
```python
# workflow node
result = interrupt({"action": "sign_contract", "contract": contract, "risk": "high"})
# sweeper (APScheduler job)
async def expire_stale_approvals():
    for row in await approval_repo.expired():
        await graph_resumer.resume(row, {"approved": False, "reason": "timeout"})
```

### Pattern 3: Durable Side-Effect Queue — Postgres Outbox + asyncio Worker

**What:** Heavy I/O jobs (crawl a website, send 25 outreach emails, render a PDF report, run 60 maintenance checks) do NOT run inline in the graph or in the scheduler thread. The producing node inserts an `outbox_events` row **in the same DB transaction** as the business state change; an asyncio worker polls with `SELECT ... FOR UPDATE SKIP LOCKED`, executes, and marks `published`/`FAILED` with retry count and exponential backoff; terminal failures go to a DLQ state.

**When to use:** Any job that (a) is slow (minutes), (b) must survive restarts, (c) needs retries, or (d) must not be duplicated. This is the classic transactional outbox pattern (verified: polling publisher with `FOR UPDATE SKIP LOCKED`, `(status, created_at)` index, idempotent consumers — microservices.io + multiple production references).

**Trade-offs:** Poll latency (2s tick is fine here); at-least-once means consumers must be idempotent (e.g., crawl job keyed by `business_id` — re-running overwrites the same `audits` row). Redis+arq/Celery become worthwhile only at much higher volumes; Postgres outbox = zero new infra, transactional consistency with the deal state — ideal for a free-tier/Supabase budget.

**Example:**
```python
async with session.begin():
    audit = Audit(business_id=biz.id)
    session.add(audit)
    session.add(OutboxEvent(type="crawl_website",
                            payload={"business_id": str(biz.id)}, aggregate_id=biz.id))
# worker:
rows = await session.execute(text(
    "SELECT ... FROM outbox_events WHERE status='PENDING' ORDER BY created_at "
    "LIMIT 20 FOR UPDATE SKIP LOCKED"))
```

### Pattern 4: Layered Crawl — robots policy → rate limiter → fetch → (Playwright escalation)

**What:** Every crawl passes three gates before a single request: (1) `urllib.robotparser` (stdlib) `can_fetch(user_agent, url)` — cached per domain with TTL, hard-fail closed (deny by default on parse failure, log it); (2) per-domain token-bucket rate limiter with randomized jitter and a global concurrency cap (config: `daily_lead_discovery_count`, crawl delay); (3) an `audits`/crawl-job row keyed by business_id for dedupe + resume. Fetch cheap pages with httpx; escalate to Playwright only when the page needs JS rendering or when SPEC-002 metrics (Core Web Vitals, a11y) require a real browser context — run Playwright in a subprocess/isolated worker so browser crashes don't take down the API.

**When to use:** All website audits and any directory/social scraping. SPEC-002 mandates "Rate Limit Compliance 100% / Robots.txt Compliance 100%" and PROJECT.md makes it a legal gate — this pattern is non-negotiable, not a nicety.

**Trade-offs:** Hand-rolled = full control, ~200 lines (robotparser + token bucket + semaphores). **Crawlee for Python** (Apache-2.0, by Apify) is the verified turnkey alternative: `BasicCrawler(respect_robots_txt_file=True)` skips disallowed URLs automatically, manages per-domain concurrency, retries, and has `AdaptivePlaywrightCrawler` that auto-decides HTTP vs browser per request — all async. Verdict: **start with the hand-rolled layered fetch for audits v1 (fewer deps, full compliance control), adopt Crawlee the moment crawling breadth exceeds ~3 sources or JS rendering becomes common.**

### Pattern 5: Decision Log — append-only table, not an event store

**What:** One `decision_events` table (SPEC-001 §8.4 shape): entry_id UUID, ts, agent_id, action, decision, rationale, inputs JSON, outputs JSON, confidence, human_reviewed, correlation_id (pipeline run id), version. Rows are INSERT-only; no UPDATE/DELETE by application code (compliance export + 7-year retention via table partitioning or archival job). All graph nodes and workers write through a single `AuditService` so the correlation_id is always populated.

**When to use:** Immediately — SPEC-001 FR-017..020 (immutable log, correlation IDs, PII redaction at write time, export endpoint). It also doubles as the debugging substrate: "show me every decision that produced this contract" is one indexed query.

**Trade-offs:** Do NOT build a separate event stream (Kafka/EventStore) for this — single-operator volume (tens of thousands of decisions/year) doesn't need one, and the DB log is queryable/exportable which a stream alone isn't. If live dashboard updates are wanted later, add Postgres `LISTEN/NOTIFY` or Redis pub/sub on top of the same table; the table remains the source of truth.

### Pattern 6: Scheduler + Worker Separation

**What:** APScheduler `AsyncIOScheduler` runs inside the FastAPI process (lifespan), owning: daily pipeline trigger (enqueues a "run daily discovery" outbox job), approval-expiry sweeper, stuck-job recovery sweeper, maintenance-check triggers, upsell-health triggers. **Scheduler jobs never do the work** — they enqueue outbox events and return. A separate asyncio worker process (`python -m backend.worker`) drains the outbox. The API process stays responsive; the worker can be scaled/restarted independently.

**When to use:** From day one — it costs nothing extra and prevents the classic "BackgroundScheduler doing heavy work inside the web process" failure (blocks the event loop, loses jobs on restart).

**Trade-offs:** Two processes to run (uvicorn + worker) — trivial with a Procfile/supervisor. If single-process-only deployment is ever forced, the worker can run as an asyncio task inside the same process (degraded but workable).

## Data Flow

### End-to-End Pipeline (the daily agency cycle)

```
APScheduler (daily 08:00)
    ↓ enqueue
outbox: run_daily_cycle
    ↓ worker → CEO supervisor graph
CEO plans day (lead budget from settings.daily_lead_discovery_count)
    ↓
[DISCOVERY GRAPH]  scanner → collector (dirs/search/social) → enrich → score(0-100)
    ↓ businesses + audits rows, decision_events written each step
priority queue (Business.priority_score, status=DISCOVERED)
    ↓ (score ≥ threshold)
[DELIVERY-LEAD GRAPH: audit stage]  crawl job (outbox) → AuditAgent scoring
    ↓ audits row (perf/SEO/a11y scores, tech stack, opportunities, ROI estimate)
[SALES GRAPH]  proposal (pricing engine: hours×complexity×market×ROI → price bounds)
    → negotiation (guardrails: never below min_price; escalation)
    → ⛔ GATE: contract generation → interrupt() → owner approves
    → legal: SOW/contract/NDA render (Jinja2 templates) → send for signature
    → ⛔ GATE: payment schedule → interrupt() → owner approves
[FINANCE]  payment collection (Razorpay/Stripe, recurring billing, reminders)
    ↓ contract.status=EXECUTED, payment received
[DELIVERY GRAPH]  project creation → task generation → design → dev → QA → deploy
    → ⛔ GATE: go-live confirmation (only if outside pricing rules)
[MAINTENANCE]  monthly checks (SSL/uptime/links/SEO/security/deps) → client report
[GROWTH]  usage analytics → health score → upsell/referral triggers
```

### Key Data Flows

1. **Scheduler → Outbox → Worker → Graphs:** APScheduler enqueues; worker claims with SKIP LOCKED; graphs run; nodes write business rows + outbox rows + decision rows in the same transactions.
2. **Agent → DB (via repositories):** every agent outcome persisted immediately (fixes today's mock-data agents that never touch the DB — CONCERNS.md "Unwired persistence").
3. **Approval round-trip:** graph interrupt → `approval_requests` row → dashboard poll/notify → owner respond → API resumes graph via `Command(resume=...)` → graph continues → `decision_events` append.
4. **Human review loop for audit:** crawler stores `raw_crawler_data` JSON; AuditAgent scores from it; the LLM never re-fetches (deterministic scores, auditable inputs).
5. **Webhooks in, outbox out:** payment webhooks (Razorpay/Stripe) land in FastAPI, immediately enqueue reconciliation jobs — no webhook handler ever does inline work.

### State Management

- **Runtime:** LangGraph checkpoints in Postgres (`PostgresSaver`) keyed by `thread_id` (= pipeline_run_id). This replaces the current mutable `AgentContext` object-reference passing (`base.py:14`) — context becomes typed graph state, versioned per checkpoint.
- **At rest:** existing SQLAlchemy models (businesses → audits → proposals → contracts → projects → tasks → maintenance_checks → outreach_logs) + new `approval_requests`, `outbox_events`, `decision_events`, `pipeline_runs` tables. Status enums already model the pipeline (BusinessStatus, ProposalStatus, ContractStatus, etc.).
- **Ephemeral:** none needed in v1 — no Redis dependency for core flow (Redis stays optional for rate-limit/caching later). This contradicts SPEC-001's Redis bus but matches the free-tier constraint; document the deviation.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **Now (v1): 10-50 leads/day, 1 owner** | Single API process + single worker process; Postgres outbox; PostgresSaver checkpoints. Postgres pool 10/20 (already configured) is ample. SPEC-001's NFR targets (10k msg/s, 100+ agents, 99.9% k8s) are **aspirational and mismatched with the free-tier budget — do not design for them now** |
| **10x: 500 leads/day, 2-3 staff** | Add Redis (Upstash free tier): rate-limit counters, response caching, pub/sub for dashboard live updates. Consider arq (async Redis queue) if outbox poll latency or volume becomes limiting. Add a second worker process. Move crawler to its own process (Playwright isolation) |
| **100x: 5k+ leads/day, agency scale** | Then — and only then — evaluate Temporal for the long-running financial/legal flows (durable execution, audit-grade guarantees; the LangChain ecosystem's own position: "LangGraph builds your agents, Temporal executes workflows — many teams run both"). Split services. This is the documented escalation path, not a v1 requirement |

### Scaling Priorities

1. **First bottleneck:** LLM provider rate limits + cost — already anticipated (config has daily limits; add per-provider token budget enforcement + caching keyed on (model, messages-hash)). Multi-provider fallback exists in `base.py` but has no retry/backoff — add before any autonomous volume.
2. **Second bottleneck:** Playwright concurrency (browser processes are heavy). Mitigation: keep Playwright in a dedicated worker with a hard concurrency cap (2-3 contexts), HTTP-first fetching for the bulk.

## Anti-Patterns

### Anti-Pattern 1: Keyword-string agent dispatch
**What people do:** Route agent tasks by substring matching on free text (`"discover" in task.lower()` — the current `lead_hunter.py:50` / `ceo.py:41` pattern).
**Why it's wrong:** Ambiguous compound tasks match the wrong branch; a renamed word silently changes behavior; impossible to validate or type-check. CONCERNS.md flags this as fragile.
**Do this instead:** Typed task payloads (`task_type: Literal["discover","enrich","score",...]` + Pydantic schema). LangGraph nodes make this structural — the node itself IS the typed entry point.

### Anti-Pattern 2: Message bus as control flow
**What people do:** Publish events for every step and have agents subscribe to decide the next step ("event-driven orchestration").
**Why it's wrong:** Control flow becomes implicit, un-debuggable, and un-resumable; approval gates require building a hand-rolled pending-state machine; "what's the state of this deal?" has no answer. SPEC-001's message-bus FRs (pub/sub, DLQ, priorities) push this way.
**Do this instead:** State machines own control flow (Pattern 1); the queue owns only side-effect jobs (Pattern 3). Message bus features that genuinely matter (DLQ, retries) exist in the outbox table.

### Anti-Pattern 3: Approval as a bare boolean column
**What people do:** `human_approval_required` flag with no workflow (the current `Proposal` model) — CEOAgent already "approves" with no data (`_review_proposal` returns APPROVED unconditionally unless the flag is set — a compliance hole flagged in CONCERNS.md).
**Why it's wrong:** Nothing suspends, nothing resumes, nothing records who approved what with what context; auditability and escalation are impossible.
**Do this instead:** Pattern 2 — `approval_requests` rows with context snapshots, expiry, and decision_events recording.

### Anti-Pattern 4: Crawling without a compliance gate
**What people do:** Fire Playwright/httpx at any URL from the agent code.
**Why it's wrong:** robots.txt violations and rate-limit blowups are the stated legal risk of this product (PROJECT.md compliance constraints; SPEC-002 mandates 100% compliance). IP bans kill the pipeline's data source.
**Do this instead:** Pattern 4 — a single `crawler` service every fetch path goes through; robots policy deny-by-default; per-domain token buckets; audit log records every crawl request (also proves compliance).

### Anti-Pattern 5: Heavy work in scheduler jobs / BackgroundTasks
**What people do:** APScheduler `BackgroundScheduler` running crawls inline, or FastAPI `BackgroundTasks` for email sends.
**Why it's wrong:** Blocks the event loop (API latency spikes), jobs are lost on restart/deploy, no retries, no visibility. Verified against ecosystem consensus (BackgroundTasks = in-process, killed on restart; "must-run" work belongs in a queue).
**Do this instead:** Pattern 6 — scheduler enqueues, worker drains.

### Anti-Pattern 6: Dual source roots (`backend/` + `src/`)
**What people do:** Keep the empty `src/` scaffold and let new code land in either tree (CONCERNS.md "two competing source roots").
**Why it's wrong:** Split-brain imports, duplicated package discovery, confused tooling config.
**Do this instead:** Single `backend/` package (see verdict), delete `src/`, document in STRUCTURE.md.

### Anti-Pattern 7: Redis/Kafka for everything "because SPEC-001 says so"
**What people do:** Stand up Redis queues + Kafka + Kubernetes to satisfy the spec's NFRs (10k msg/s, 99.9%).
**Why it's wrong:** A solo/owner-operated free-tier deployment can't operate that stack; it adds failure modes, not reliability, at this volume. SPEC-001 was written aspirational; the roadmap must re-derive it pragmatically.
**Do this instead:** Postgres-first (outbox, checkpoints, decision log). Escalate infra only at the documented scaling thresholds.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LLM providers (OpenRouter/Groq/Gemini) | Direct httpx calls via existing `BaseAgent.call_llm`; wrap with retry/backoff + per-provider rate limiter + response cache | **Fix:** move Gemini API key from URL query string to `X-Goog-Api-Key` header (CONCERNS.md security); error strings must become typed exceptions/`success:False` |
| Supabase (Postgres) | SQLAlchemy async engine (existing `database.py`); Alembic migrations replace `create_all` | `create_all` on every worker start races across processes — migrations fix it |
| Playwright | Dedicated crawler worker process; browser install documented + pinned in CI | `playwright install` step is missing from tooling today |
| SendGrid (email outreach) | Outbox jobs; enforce `daily_outreach_limit` at enqueue time; unsubscribe/opt-out + physical address in every send (CAN-SPAM/GDPR/DPDP) | Spec'd in SPEC-003 FR-014 — compliance, not feature |
| Razorpay/Stripe | Webhook → FastAPI → outbox reconciliation job; idempotent by `payment_intent_id` | `stripe>=7.0.0` pin is 6+ majors stale — bump at finance phase |
| Vercel/Cloudflare/Netlify/Railway | Delivery agent's deploy tooling; deployment URLs stored on `projects` | Auto-config (analytics/SEO/monitoring) per SPEC-004 |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| API ↔ Orchestration | HTTP + in-process service calls; resumes via `Command(resume=...)` | API never runs agents directly |
| Graphs ↔ Agents | Direct node calls (typed) | Agents become nodes; `BaseAgent` stays as LLM-call core |
| Graphs ↔ Outbox | Same-transaction insert (unit of work) | Guarantees no lost jobs |
| Worker ↔ Services | Direct calls (crawler, email, report) | Worker is the only component that executes outbox jobs |
| All components ↔ Decision Log | `AuditService` (append-only) | Single write path guarantees correlation_ids |
| Dashboard ↔ API | REST (JWT) | No WebSocket in v1; polling + `GET /approvals?status=pending` is fine at this volume |

## Build Order (dependencies between components)

1. **Foundation (blocks everything):** package layout fix (delete `src/`, `__init__.py`, installable build, README.md, dependency pins incl. `langgraph` unpin), Alembic migrations, FastAPI entry + lifespan, repositories, new tables (`approval_requests`, `outbox_events`, `decision_events`, `pipeline_runs`), auth. *Addresses: CONCERNS.md's "No entry point / no migrations / no repositories / dual roots".*
2. **Orchestration core (blocks all pipeline phases):** LangGraph skeleton — checkpointer, one generic pipeline state machine, typed task protocol replacing keyword dispatch, Approval Engine + API endpoints, APScheduler + outbox worker. *Proves the suspend/resume loop end-to-end with the CEO/LeadHunter agents already written.*
3. **Discovery (first value):** crawler service (Pattern 4) + lead collection + enrichment + scoring as outbox jobs; daily cycle wired. *De-risk: compliance gates land before any real crawling.*
4. **Sales:** audit → proposal (pricing engine) → negotiation (guardrails exist in `base.py:219`) → contract gate (first real approval gate).
5. **Legal + Finance:** template rendering, signature flow, payment collection + webhooks, MRR dashboard. *Gates are already built in phase 2 — here they get their first financial teeth.*
6. **Delivery:** project/tasks → design → dev → QA → deploy automation.
7. **Maintenance + Growth:** monthly checks, client reports, upsell triggers.

**Ordering rationale:** phases 1-2 are pure infrastructure with zero external risk; phase 3 introduces the only legally-sensitive external interaction (crawling) while the system is still cheap to fail; phases 4-5 put money in motion only after the approval mechanism has been exercised; phases 6-7 consume everything prior. The approval gate pattern is built once (phase 2) and reused, not re-invented per department.

---

## Sources

- LangGraph official docs — interrupts / human-in-the-loop: https://docs.langchain.com/oss/python/langgraph/interrupts ("graph will wait indefinitely until resumed"; `Command(resume=...)`) — HIGH
- LangGraph official docs — persistence/checkpointers: https://docs.langchain.com/oss/python/langgraph/persistence, `PostgresSaver` usage in https://docs.langchain.com/oss/python/langgraph/add-memory — HIGH
- LangChain vs Temporal comparison (vendor, 2026-06): https://www.langchain.com/resources/langgraph-vs-temporal — MEDIUM (vendor source, consistent with independent analyses)
- Independent LangGraph vs Temporal 2026 analyses: https://agentmarketcap.ai/blog/2026/04/08/langgraph-vs-temporal-long-running-agent-workflows-2026, https://inferensys.com/comparisons/agentic-workflow-orchestration-frameworks/langgraph-vs-temporal-for-agent-workflows — MEDIUM (agree on: LangGraph = agent-native in-memory graphs + HITL; Temporal = durable execution platform, heavyweight; hybrid pattern common)
- Orchestration framework landscape 2026: https://presenc.ai/research/multi-agent-orchestration-frameworks-2026 — MEDIUM (framework choice "matters at the margin"; human-checkpoint design is the primary success factor)
- APScheduler vs Celery: https://ceylan.co.at/learn/apscheduler-vs-celery (2026-04), https://techoral.com/python/celery-beat-apscheduler.html, https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat (2025-09) — MEDIUM (consistent consensus)
- FastAPI BackgroundTasks unreliability for must-run work: https://stackoverflow.com/questions/79883964 — MEDIUM
- Transactional outbox pattern: https://microservices.io/patterns/data/transactional-outbox.html; https://codably.dev/architecture/the-transactional-outbox-pattern-reliable-event-publishing-explained; zylos.ai research (2026-06) incl. `FOR UPDATE SKIP LOCKED` + `(status, created_at)` index operational checklist — HIGH (established pattern, multiple independent sources)
- PyPA src vs flat layout: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ — HIGH (official)
- pydevtools handbook src vs flat (2026-06): "Use the flat layout when building an application you run directly and never publish" — MEDIUM
- Crawlee for Python robots.txt + architecture: https://crawlee.dev/python/docs/examples/respect-robots-txt-file, https://crawlee.dev/python/docs/guides/architecture-overview (respect_robots_txt_file, AdaptivePlaywrightCrawler) — HIGH (official)
- `urllib.robotparser` (stdlib) robots.txt parsing — HIGH (Python stdlib)
- Microsoft Agent Framework human-approval workflow checkpointing (2025-10): https://argonsys.com/microsoft-cloud/library/multi-agent-workflow-with-human-approval-using-agent-framework — LOW/MEDIUM (corroborates the pause-at-checkpoint/resume pattern across frameworks)

---

*Architecture research for: AI Agency OS — autonomous AI-powered digital agency platform*
*Researched: 2026-08-04*
