# Phase 1: Foundation & Orchestration Core - Context

**Gathered:** 2026-08-04
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase makes the platform's plumbing production-ready and proves the owner's trust mechanism end-to-end. Delivers: installable package with current declared dependencies and a committed `uv.lock`; Alembic migrations (no `create_all`); an append-only audit log queryable by correlation ID; hard LLM-spend and outreach-volume budget caps enforced in code; a heartbeat-monitored scheduler; compliance middleware (robots.txt deny-by-default, per-domain token-bucket rate limits, anti-spam volume caps, consent records + suppression list + one-click unsubscribe); session auth for the single owner; and a LangGraph 1.x approval engine with an owner-facing approval queue that pauses and resumes agent workflows — proven with the existing CEO/LeadHunter agents. Also repairs the known codebase defects (11 NotImplementedError stubs, mock-data agent path, fake auto-approval, `get_db()` init ordering, `datetime.utcnow`, Gemini key in URL query, missing `__init__.py`, undeclared `sqlalchemy`, ancient `langgraph>=0.0.30` pin, no migrations, no CI, no README).

Scope anchor: 13 requirements — FND-01..07, CMP-01..04, DASH-01, DASH-03.

Out of scope (belongs to later phases): real lead discovery/enrichment (Phase 2), website audit crawling with Playwright (Phase 2), outreach sequences and email sending (Phase 3), pricing/negotiation (Phase 3), contracts/payments (Phase 4), full Next.js dashboard (Phase 2), pgvector embeddings (Phase 2).

</domain>

<decisions>
## Implementation Decisions

### Package Layout & Dependencies (FND-01, FND-02)
- **D-01:** Flat layout — `backend/` is the single installable package; delete the empty `src/` scaffold; add `__init__.py` to `backend/` and `backend/agents/`; install via `pip install -e .` from repo root.
- **D-02:** uv as the package manager; commit `uv.lock`; `pyproject.toml` remains the source of truth. Create the missing `README.md` (referenced by `pyproject.toml`).
- **D-03:** Bump to research-verified current versions: FastAPI 0.141.1, SQLAlchemy 2.x (declare it — currently undeclared), asyncpg, redis 8.1.0, supabase 2.31, httpx 0.28.1, langgraph 1.2.10, langchain-core (transitive, >=1.4.7), pydantic 2 + pydantic-settings, uvicorn, loguru, apscheduler, alembic (new), jinja2, python-multipart, itsdangerous (new — session cookies), pwdlib[argon2] (new — replaces passlib), PyJWT (new — replaces python-jose).
- **D-04:** Remove unused declared deps to cut supply-chain surface; re-add in the consuming phase: playwright (Phase 2), stripe/razorpay (Phase 4), sendgrid (Phase 3), openai/langchain-openai (Phase 3+), python-jose, passlib[bcrypt], python-dotenv (redundant — pydantic-settings loads `.env` itself).

### Database & Migrations (FND-03)
- **D-05:** Alembic replaces `Base.metadata.create_all`; initial revision generated; startup runs `alembic upgrade head` (or documented explicit step); dev DB is local PostgreSQL (docker-compose provided) or Supabase; `get_db()` init ordering fixed (engine/session created before first use — currently TypeError); fail fast when `DATABASE_URL` missing.
- **D-06:** Money fields switch from `float` to `Decimal` (`Numeric(12,2)`) across models and config pricing data.

### Audit Log (FND-04)
- **D-07:** Append-only audit log table (actor: agent/owner/system, action, entity type+id, payload JSON, correlation_id, timezone-aware created_at); single `AuditService` write path; no UPDATE/DELETE ever; queryable by correlation_id for lead/proposal/contract trails. `datetime.utcnow` removed everywhere.

### Approval Engine (FND-05)
- **D-08:** Adopt LangGraph 1.x as new work — the `langgraph>=0.0.30` pin and any 0.0.x-API usage are deleted. Agent workflows become LangGraph StateGraphs with `interrupt()`/`Command(resume=...)` approval nodes and durable checkpoints (`PostgresSaver`).
- **D-09:** An `approval_requests` table mirrors gated actions for the queue UI; APScheduler sweeper expires/escalates stale requests; approve → resume paused workflow, reject → halt with reason.
- **D-10:** CEO's fake auto-approval is removed; below-threshold auto-approve (if kept) requires evidence fields; gated actions per success criteria: contracts, payments, below-floor offers, legal changes.

### Budget Caps (FND-06)
- **D-11:** Caps enforced in code at enforcement points (never by LLM): per-provider LLM spend counters with hard-block before the call, outreach send caps; breach → audit event + alert; caps configurable via settings.

### Scheduler (FND-07)
- **D-12:** APScheduler `AsyncIOScheduler` in-process; job functions only enqueue work (no long inline tasks); heartbeat job writes heartbeat row; sweeper jobs (approval expiry, budget window reset); silent-failure alert to owner.

### Compliance Middleware (CMP-01..CMP-04)
- **D-13:** robots.txt: fetched once per domain (robotparser-based), deny-by-default, TTL-cached; fetch pipeline = robots check → per-domain token-bucket rate limiter with jitter → httpx; Playwright only for JS-rendered pages (Phase 2).
- **D-14:** Anti-spam layer in foundation: daily volume caps, consent records, suppression list consulted before any send, one-click unsubscribe endpoint + physical address requirement, lawful-basis recorded — sending infrastructure itself lands in Phase 3, the compliance choke points are built now.
- **D-15:** Compliance applied at single choke points (HTTP client factory + send service) so no code path can bypass.

### Auth & Phase 1 UI (DASH-01, DASH-03)
- **D-16:** Single-owner auth: email+password, password hashed with pwdlib[argon2], signed HttpOnly/Secure/SameSite session cookie (itsdangerous); owner seeded from env config.
- **D-17:** Phase 1 UI is minimal server-rendered FastAPI + Jinja2 (login page, approval queue page with approve/reject/escalate); the full Next.js 16 frontend is deferred to Phase 2 when the dashboard scope lands.

### Observability & Quality
- **D-18:** loguru sink configured with secret redaction; Gemini key moved from URL query into headers (currently in URL — leak risk).
- **D-19:** GitHub Actions CI: ruff → black --check → mypy → pytest; baseline tests for config validation, guardrail math, LLM client error paths, DB lifecycle, and the approval round-trip.

### Mock Mode
- **D-20:** `MOCK_MODE` env gate retained for dev-only mock agent data, default off; CEO auto-approval behavior removed entirely.

### Claude's Discretion
- Approval queue page UX details, exact scheduler cadences, alert channel wiring (log-based for now), file naming, and minor structural choices are left to the planner/implementer's judgment.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Requirements
- `.planning/ROADMAP.md` §Phase 1 — goal, mode (mvp), success criteria (5 items), UI hint: yes
- `.planning/REQUIREMENTS.md` — full definitions of FND-01..07, CMP-01..04, DASH-01, DASH-03 (section "Requirements Detail"); traceability table lines 156-171
- `.planning/specs/core/SPEC-001-core-system-architecture.md` — canonical architecture: orchestration, approval workflow, audit log, compliance, agent framework
- `.planning/specs/discovery/SPEC-002-lead-discovery-engine.md` §5/§7 — compliance requirements for the crawler (robots.txt, rate limiting)
- `.planning/specs/sales/SPEC-003-sales-proposal-system.md` §FR-014 — anti-spam / unsubscribe requirements

### Research Verdicts (dependency of D-01..D-20)
- `.planning/research/SUMMARY.md` — consolidated verdicts: LangGraph 1.x `interrupt()`/`PostgresSaver`, Postgres outbox, APScheduler enqueue-only, uv lockfile, Alembic, pwdlib/PyJWT, compliance-in-foundation, guardrails via tool-call schemas
- `.planning/research/STACK.md` — verified current versions for every dependency bump in D-03
- `.planning/research/ARCHITECTURE.md` — approval-engine design research (interrupt/resume patterns)
- `.planning/research/PITFALLS.md` — legal/technical risk evidence driving the compliance middleware (CAN-SPAM, DPDP, injection, webhook idempotency, scheduler heartbeats)

### Existing Code Insights (the code this phase repairs)
- `.planning/codebase/CONCERNS.md` — full defect list Phase 1 must fix (stubs, mock data, fake approval, get_db TypeError, utcnow, URL-query key, no auth, placeholder defaults, no migrations, unused deps)
- `.planning/codebase/ARCHITECTURE.md` — as-built agent framework (BaseAgent/AgentContext/role bases, string-keyword dispatch) to refactor into LangGraph workflows
- `.planning/codebase/STACK.md` — declared deps vs reality (sqlalchemy gap, langgraph ancient pin, no lockfile, missing README)
- `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/TESTING.md`, `.planning/codebase/INTEGRATIONS.md` — layout, style (black 100 / ruff / mypy strict), and test conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseAgent`/`AgentContext`/`LLMAgent` (`backend/agents/base.py:14,25,145`) — keep and refactor rather than rewrite; becomes the LLM-call layer inside LangGraph nodes
- Multi-provider LLM dispatch (`backend/agents/base.py:54-125`) — keep; fix Gemini key handling (URL query → header)
- `NegotiationAgent.check_guardrails` (`backend/agents/base.py:219`) — only implemented role-base method; pattern for code-enforced guardrails (extend to budget caps, D-11)
- 9 SQLAlchemy models + 7 status enums (`backend/database.py:89-260`) — migration source; money fields → Decimal (D-06)
- `Settings` singleton with UPPER_SNAKE env aliases (`backend/config.py:8,176`) — extend for caps, compliance, owner credentials
- Result-envelope pattern `{"success": bool, "data", "raw"}` — keep as agent output contract

### Established Patterns
- Async-only runtime — all agents/DB async; LangGraph nodes must be async
- Env-driven config via pydantic-settings — new caps/compliance settings follow this pattern
- Black 100 / ruff / mypy strict (`disallow_untyped_defs`, `warn_return_any`) — all new code must satisfy these (CI gates, D-19)

### Integration Points
- New FastAPI app entry (`backend/main.py`) wires lifespan: DB init → Alembic upgrade → scheduler start → heartbeat
- Approval queue reads `approval_requests` table; approve/reject resume LangGraph threads via `Command(resume=...)`
- `AuditService` is called by every agent/owner action; correlation_id threaded through `AgentContext`
- Compliance middleware wraps the httpx client that `base.py` uses for all outbound fetches
- String-keyword `execute()` dispatch replaced by LangGraph workflows; keep thin adapter for existing callers
</code_context>

<specifics>
## Specific Ideas

- Success criterion 3: the approval round-trip must be proven with the existing CEO/LeadHunter agents — pause on gated action, owner approves from the queue, workflow resumes and completes. Use this as the acceptance test.
- Queue UI must show what's being gated (amount, entity, details) so the owner can decide without leaving the page (per PRD approval queue concept).
- Success criterion 2: audit log queryable by correlation ID per lead/proposal/contract — design correlation_id propagation through `AgentContext` from day one.
- Compliant-outreach middleware (CMP-03/CMP-04) is built in this phase even though sending lands in Phase 3 — the choke points, suppression list, consent records, and unsubscribe route must exist before any real send can happen.

</specifics>

<deferred>
## Deferred Ideas

- Playwright crawl engine and browser fetch path → Phase 2 (compliance choke points built now)
- Full Next.js 16 frontend + shadcn/ui + recharts dashboard → Phase 2 (DASH-02)
- Stripe/Razorpay SDKs and webhook idempotency implementation → Phase 4 (design research done in PITFALLS.md)
- pgvector embeddings for dedup/matching → Phase 2
- Sentry/alert notification channel beyond logging → when monitoring scope grows (Phase 6)

</deferred>

---

*Phase: 1-Foundation & Orchestration Core*
*Context gathered: 2026-08-04*
