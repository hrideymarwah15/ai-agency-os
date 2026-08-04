# Phase 1: Foundation & Orchestration Core - Research

**Researched:** 2026-08-04
**Domain:** Python/FastAPI/SQLAlchemy async brownfield rebuild — package/dependency repair, Alembic migrations, append-only audit log, LangGraph 1.x approval engine, budget caps, heartbeat scheduler, compliance middleware, session auth
**Confidence:** HIGH (stack versions verified against PyPI JSON API 2026-08-04; LangGraph interrupt/checkpoint APIs verified against official docs; slopcheck 0.6.1 scan: 22/22 packages OK)

## Summary

Phase 1 is a brownfield foundation rebuild of an installable-but-broken skeleton: `pyproject.toml` declares 24 deps of which `sqlalchemy` is missing (clean installs fail at import), `langgraph>=0.0.30` is a pre-1.0 pin whose API no longer exists, there is no lockfile, no FastAPI entry point, no migrations, no tests, no CI, and the compliance/audit/approval machinery mandated by FND-04..07 + CMP-01..04 + DASH-01/03 exists only as config values. The phase delivers those mechanics and proves the owner's trust loop end-to-end with the existing CEO/LeadHunter agents.

Research verdicts, all verified this session: **(1)** LangGraph 1.2.10's `interrupt()`/`Command(resume=...)` is the purpose-built durable approval gate — graph suspends at a checkpoint, `approval_requests` table mirrors pending state for the queue UI, and the API resumes via `Command(resume=...)` with the same `thread_id`; `AsyncPostgresSaver` (3.1.1) persists checkpoints via **psycopg 3**, independent of the SQLAlchemy/asyncpg engine. **(2)** All pinned versions (FastAPI 0.141.1, SQLAlchemy 2.0.51, Alembic 1.18.5, itsdangerous 2.2.0, pwdlib 0.3.0, APScheduler 3.11.3) exist at the researched versions and — verified wheel-by-wheel — all binary deps (asyncpg, greenlet, argon2-cffi-bindings via abi3, psycopg-binary, orjson) have Python 3.14.5 wheels; the dev machine is install-ready. **(3)** Environment: PostgreSQL 15.18 installed but **not running** (docker-compose from D-05 or `brew services start` needed — this is the phase's only environmental blocker), Redis absent (in-process token bucket is the D-13-consistent choice), uv 0.9.27 and Docker 28.5.1 available.

**Primary recommendation:** Plan the phase as nine parallelizable workstreams — (1) packaging/deps (flat `backend/` package, uv.lock, README, .gitignore), (2) DB layer (Alembic + model repairs: Decimal money, tz-aware timestamps, callable JSON defaults, URL-safe engine creation, fail-fast get_db), (3) append-only audit log + AuditService + tamper-proof DB trigger, (4) session auth (itsdangerous cookies + pwdlib argon2) + Jinja2 login, (5) LangGraph CEO/LeadHunter graphs with approval gate + PostgresSaver, (6) approval_requests table + queue API + resume endpoints + sweeper, (7) budget caps (atomic counters, hard-block before call/send), (8) scheduler (AsyncIOScheduler in lifespan, heartbeat rows, enqueue-only jobs), (9) compliance middleware (robots deny-by-default cache, per-domain token bucket with jitter, suppression list + consent records + one-click unsubscribe) + CI. Success criterion 3 (approval round-trip with real agents) is the capstone acceptance test and should be planned as the last task with the other workstreams' outputs as dependencies.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Package Layout & Dependencies (FND-01, FND-02)**
- **D-01:** Flat layout — `backend/` is the single installable package; delete the empty `src/` scaffold; add `__init__.py` to `backend/` and `backend/agents/`; install via `pip install -e .` from repo root.
- **D-02:** uv as the package manager; commit `uv.lock`; `pyproject.toml` remains the source of truth. Create the missing `README.md` (referenced by `pyproject.toml`).
- **D-03:** Bump to research-verified current versions: FastAPI 0.141.1, SQLAlchemy 2.x (declare it — currently undeclared), asyncpg, redis 8.1.0, supabase 2.31, httpx 0.28.1, langgraph 1.2.10, langchain-core (transitive, >=1.4.7), pydantic 2 + pydantic-settings, uvicorn, loguru, apscheduler, alembic (new), jinja2, python-multipart, itsdangerous (new — session cookies), pwdlib[argon2] (new — replaces passlib), PyJWT (new — replaces python-jose).
- **D-04:** Remove unused declared deps to cut supply-chain surface; re-add in the consuming phase: playwright (Phase 2), stripe/razorpay (Phase 4), sendgrid (Phase 3), openai/langchain-openai (Phase 3+), python-jose, passlib[bcrypt], python-dotenv (redundant — pydantic-settings loads `.env` itself).

**Database & Migrations (FND-03)**
- **D-05:** Alembic replaces `Base.metadata.create_all`; initial revision generated; startup runs `alembic upgrade head` (or documented explicit step); dev DB is local PostgreSQL (docker-compose provided) or Supabase; `get_db()` init ordering fixed (engine/session created before first use — currently TypeError); fail fast when `DATABASE_URL` missing.
- **D-06:** Money fields switch from `float` to `Decimal` (`Numeric(12,2)`) across models and config pricing data.

**Audit Log (FND-04)**
- **D-07:** Append-only audit log table (actor: agent/owner/system, action, entity type+id, payload JSON, correlation_id, timezone-aware created_at); single `AuditService` write path; no UPDATE/DELETE ever; queryable by correlation_id for lead/proposal/contract trails. `datetime.utcnow` removed everywhere.

**Approval Engine (FND-05)**
- **D-08:** Adopt LangGraph 1.x as new work — the `langgraph>=0.0.30` pin and any 0.0.x-API usage are deleted. Agent workflows become LangGraph StateGraphs with `interrupt()`/`Command(resume=...)` approval nodes and durable checkpoints (`PostgresSaver`).
- **D-09:** An `approval_requests` table mirrors gated actions for the queue UI; APScheduler sweeper expires/escalates stale requests; approve → resume paused workflow, reject → halt with reason.
- **D-10:** CEO's fake auto-approval is removed; below-threshold auto-approve (if kept) requires evidence fields; gated actions per success criteria: contracts, payments, below-floor offers, legal changes.

**Budget Caps (FND-06)**
- **D-11:** Caps enforced in code at enforcement points (never by LLM): per-provider LLM spend counters with hard-block before the call, outreach send caps; breach → audit event + alert; caps configurable via settings.

**Scheduler (FND-07)**
- **D-12:** APScheduler `AsyncIOScheduler` in-process; job functions only enqueue work (no long inline tasks); heartbeat job writes heartbeat row; sweeper jobs (approval expiry, budget window reset); silent-failure alert to owner.

**Compliance Middleware (CMP-01..CMP-04)**
- **D-13:** robots.txt: fetched once per domain (robotparser-based), deny-by-default, TTL-cached; fetch pipeline = robots check → per-domain token-bucket rate limiter with jitter → httpx; Playwright only for JS-rendered pages (Phase 2).
- **D-14:** Anti-spam layer in foundation: daily volume caps, consent records, suppression list consulted before any send, one-click unsubscribe endpoint + physical address requirement, lawful-basis recorded — sending infrastructure itself lands in Phase 3, the compliance choke points are built now.
- **D-15:** Compliance applied at single choke points (HTTP client factory + send service) so no code path can bypass.

**Auth & Phase 1 UI (DASH-01, DASH-03)**
- **D-16:** Single-owner auth: email+password, password hashed with pwdlib[argon2], signed HttpOnly/Secure/SameSite session cookie (itsdangerous); owner seeded from env config.
- **D-17:** Phase 1 UI is minimal server-rendered FastAPI + Jinja2 (login page, approval queue page with approve/reject/escalate); the full Next.js 16 frontend is deferred to Phase 2 when the dashboard scope lands.

**Observability & Quality**
- **D-18:** loguru sink configured with secret redaction; Gemini key moved from URL query into headers (currently in URL — leak risk).
- **D-19:** GitHub Actions CI: ruff → black --check → mypy → pytest; baseline tests for config validation, guardrail math, LLM client error paths, DB lifecycle, and the approval round-trip.

**Mock Mode**
- **D-20:** `MOCK_MODE` env gate retained for dev-only mock agent data, default off; CEO auto-approval behavior removed entirely.

### the agent's Discretion
- Approval queue page UX details, exact scheduler cadences, alert channel wiring (log-based for now), file naming, and minor structural choices are left to the planner/implementer's judgment.

### Deferred Ideas (OUT OF SCOPE)
- Playwright crawl engine and browser fetch path → Phase 2 (compliance choke points built now)
- Full Next.js 16 frontend + shadcn/ui + recharts dashboard → Phase 2 (DASH-02)
- Stripe/Razorpay SDKs and webhook idempotency implementation → Phase 4 (design research done in PITFALLS.md)
- pgvector embeddings for dedup/matching → Phase 2
- Sentry/alert notification channel beyond logging → when monitoring scope grows (Phase 6)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FND-01 | Installable package, flat `backend/`, `__init__.py`, README | Flat-layout verdict (PyPA src-vs-flat discussion); `[tool.setuptools.packages.find] include=["backend*"]`; README.md must exist (pyproject `readme` ref) |
| FND-02 | Current deps + sqlalchemy declared + committed uv.lock | All versions verified on PyPI 2026-08-04 (see Standard Stack); 22/22 slopcheck OK; cp314 wheels verified for all binary deps |
| FND-03 | Alembic migrations replace create_all | Alembic 1.18.5 async env template; programmatic `command.upgrade(cfg, "head")`; cookbook connection-sharing pattern; CI "migrations up to date" check |
| FND-04 | Append-only audit log, correlation_id, queryable | AuditService single write path; PostgreSQL trigger rejecting UPDATE/DELETE on audit_logs; correlation_id threaded through AgentContext/graph state |
| FND-05 | Approval queue: approve/reject/escalate; resumes workflows | LangGraph `interrupt()` + `Command(resume=...)` verified (official docs); approval_requests table + sweeper; resume via same thread_id |
| FND-06 | Hard budget caps (LLM spend, outreach volume) | Atomic `UPDATE ... WHERE spent+cost<=cap` counters; enforcement inside `call_llm` and send service (never prompt); breach → audit + alert |
| FND-07 | Heartbeat-monitored scheduler, silent-failure alert | APScheduler 3.11 AsyncIOScheduler in lifespan; heartbeat table + staleness check job; `add_listener(EVENT_JOB_ERROR)` for alerts; enqueue-only jobs |
| CMP-01 | robots.txt deny-by-default before any fetch | `urllib.robotparser` per D-13 with TTL cache; deny on parse failure; applied in the HTTP client factory (D-15 choke point) |
| CMP-02 | Per-domain token-bucket rate limit + jitter | In-process async token bucket (Redis absent locally; Redis optional per research); jitter = random sleep in (0, bucket_period]; enforced in fetch pipeline |
| CMP-03 | Anti-spam volume caps per sender/domain | `daily_outreach_limit` config enforced at send service choke point; atomic daily counter |
| CMP-04 | Consent records, lawful basis, suppression list, one-click unsubscribe | consent_records + suppression_entries tables; unsubscribe endpoint with signed token (itsdangerous `URLSafeTimedSerializer` — canonical use case); physical address from settings |
| DASH-01 | Owner login with session auth | itsdangerous `URLSafeTimedSerializer` signed cookie (HttpOnly/Secure/SameSite=Lax), pwdlib[argon2] `PasswordHash.recommended()`, FastAPI `Depends` guard |
| DASH-03 | Review/act on audit entries + approval requests | Jinja2 queue page (server-rendered per D-17); GET /approvals + POST approve/reject/escalate; audit log query endpoint by correlation_id |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Owner session auth | API / Backend | Browser / Client (cookie only) | Auth logic + DI guard live in FastAPI; browser only stores the signed cookie — never trust client-side state |
| Approval engine (interrupt/resume) | API / Backend | Database (checkpoints) | LangGraph graphs run in-process; FastAPI endpoints drive resume via `Command(resume=...)`; PostgresSaver is the durable substrate |
| Audit log | Database | API (query endpoint) | Append-only table is the system of record; API exposes correlation-id queries; DB trigger enforces immutability |
| Budget caps (LLM spend, outreach) | API / Backend | Database (atomic counters) | Enforcement points are `call_llm` and the send service (code, never LLM); atomic SQL counters prevent race bypass |
| Scheduler + heartbeat | API / Backend (process) | Database (heartbeat rows) | AsyncIOScheduler runs in-process inside lifespan; heartbeat/staleness state lives in Postgres |
| Compliance (robots, rate limits, suppression/consent) | API / Backend (services) | — | Applied at HTTP client factory + send service choke points (D-15) so no fetch/send path bypasses |
| Phase 1 UI (login, approval queue) | Frontend Server (SSR via FastAPI + Jinja2) | API / Backend | Server-rendered per D-17; pages served by FastAPI directly; no client-side logic of consequence |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | 1.2.10 | Durable graph orchestration; approval gates | `interrupt()`/`Command(resume=...)` is purpose-built HITL (official docs verified this session); pulls langchain-core>=1.4.7,<2 |
| langgraph-checkpoint-postgres | 3.1.1 | Durable suspend/resume checkpoints | `AsyncPostgresSaver`; uses **psycopg 3** + psycopg-pool (not asyncpg) — independent pool alongside the SQLAlchemy engine; `setup()` creates its tables |
| fastapi | 0.141.1 | API, auth, Jinja2 UI, lifespan wiring | Current major; native lifespan (asynccontextmanager) replaces deprecated on_event |
| uvicorn[standard] | 0.52.1 | ASGI server | Declared; current |
| sqlalchemy[asyncio] | 2.0.51 | ORM | **Must be declared** (imported today, undeclared — clean installs fail); greenlet resolves via [asyncio] extra |
| alembic | 1.18.5 | Migrations replacing create_all | Standard SQLAlchemy migration tool; async template supports async engine |
| asyncpg | 0.31.0 | Postgres async driver | cp314 wheels verified; declared |
| pydantic / pydantic-settings | 2.13.4 / 2.14.2 | Config + validation | Current majors; existing Settings class extends (caps, compliance, owner creds) |
| itsdangerous | 2.2.0 | Signed session cookies + unsubscribe tokens | Canonical Pallets signed-data library; `URLSafeTimedSerializer` gives expiry + tamper detection; itsdangerous docs list "unsubscribe link" as a first-class use case |
| pwdlib[argon2] | 0.3.0 | Password hashing | `PasswordHash.recommended()` = Argon2id; replaces unmaintained passlib; argon2-cffi-bindings has cp314 abi3 wheels (verified) |
| PyJWT | 2.13.0 | JWT (locked D-03; latent in Phase 1) | Declared per D-03; session auth uses itsdangerous — reserve PyJWT for future API tokens or swap into unsubscribe tokens; harmless to keep |
| apscheduler | 3.11.3 (`<4`) | In-process scheduling | AsyncIOScheduler in lifespan; `<4` pinned (4.x alpha); heartbeat + sweeper jobs |
| httpx | 0.28.1 | LLM transport + fetch pipeline | Existing transport in base.py; `MockTransport` gives first-class test seams |
| tenacity | 9.1.4 | Retry/backoff on LLM calls | Repairs the documented 60s-no-retry defect; retry 429/5xx with exponential backoff [ASSUMED addition beyond D-03 — flagged for planner] |
| loguru | 0.7.3 | Logging with secret redaction | Declared; D-18 requires redaction sink config |
| jinja2 | 3.1.6 | Phase 1 UI templates (D-17) | Declared; existing backend/templates/ dir |
| python-multipart | 0.0.32 | Login form parsing | Required for form POST (login page) |
| supabase | 2.31.0 | REST client (auth/storage later) | Declared; DB access stays SQLAlchemy |
| redis | 8.1.0 | Declared; optional rate-limit backing | D-03 keeps it; local Redis absent → in-process limiter for Phase 1 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.1.1 | Test runner | dev extra; bump from >=7.4 |
| pytest-asyncio | 1.4.0 | Async tests | dev extra; `asyncio_mode = "auto"` |
| pytest-cov | current | Coverage | dev extra; CI gate |
| black / ruff / mypy | current | Lint/format/types (D-19 CI gates) | Keep; line-length 100, py311 target — note mypy config runs under Python 3.14 runtime |
| reppy | 0.4.14 | Hardened robots.txt parsing | Alternative if robotparser proves insufficient (STACK.md research); D-13 locks robotparser — reppy is the documented fallback only |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-process token bucket | Redis-backed limiter | Redis absent locally; in-process is deterministic in tests and correct at single-instance scale; swap to Redis counters when multi-process deploy happens |
| urllib.robotparser | reppy 0.4.14 | robotparser is stdlib (zero deps, locked D-13) but naive on edge-case robots.txt; reppy is the hardening path if parse failures surface |
| itsdangerous cookies | JWT-in-cookie / server-side session table | itsdangerous = zero DB reads, tamper-proof, expiring; JWT adds no value for a single-owner same-origin app |
| itsdangerous for unsubscribe token | Random token stored in DB | Signed token needs no storage/rotation — the itsdangerous docs' canonical example; DB tokens add a lookup table for no gain at this scale |
| PostgresSaver (psycopg) | SQLAlchemy engine reuse | langgraph-checkpoint-postgres manages its own psycopg pool — do NOT try to share the asyncpg engine; two connections to the same DB is normal and documented |

**Installation:**
```bash
uv add "fastapi>=0.141,<0.142" "uvicorn[standard]>=0.52,<0.53" "pydantic>=2.13" "pydantic-settings>=2.14"
uv add "sqlalchemy[asyncio]>=2.0.51,<2.1" "asyncpg>=0.31,<0.32" "alembic>=1.18,<1.19" "supabase>=2.31,<2.32"
uv add "redis>=8.1,<9" "httpx>=0.28,<0.29" "tenacity>=9.1"
uv add "langgraph>=1.2,<2" "langgraph-checkpoint-postgres>=3.1,<4"
uv add "itsdangerous>=2.2,<3" "pwdlib[argon2]>=0.3" "pyjwt>=2.13,<3"
uv add "apscheduler>=3.11,<4" "loguru>=0.7" "jinja2>=3.1" "python-multipart>=0.0.32"
uv add --dev "pytest>=9" "pytest-asyncio>=1.4" "pytest-cov" "black" "ruff" "mypy"
uv lock && uv sync
```
Note: upper bounds `<major+1>` protect the next resolver pass from silent major jumps; `uv.lock` is the real pin. APScheduler MUST stay `<4` (4.x alpha). Do NOT add playwright/stripe/razorpay/sendgrid/openai/langchain-openai/python-jose/passlib/python-dotenv per D-04.

**Version verification (2026-08-04, PyPI JSON API):** langgraph 1.2.10 ✓, langgraph-checkpoint-postgres 3.1.1 ✓, fastapi 0.141.1 ✓, sqlalchemy 2.0.51 ✓, alembic 1.18.5 ✓, itsdangerous 2.2.0 ✓, pwdlib 0.3.0 ✓, apscheduler 3.11.3 ✓, redis 8.1.0 ✓, httpx 0.28.1 ✓, pydantic 2.13.4 ✓, pydantic-settings 2.14.2 ✓, PyJWT 2.13.0 ✓, tenacity 9.1.4 ✓, asyncpg 0.31.0 ✓, supabase 2.31.0 ✓, pytest 9.1.1 ✓, pytest-asyncio 1.4.0 ✓. Python 3.14.5 wheels verified for: asyncpg (cp314), greenlet (cp314), psycopg-binary 3.3.4 (cp314), argon2-cffi-bindings 25.1.0 (cp39-abi3 — covers 3.14), cffi, bcrypt, orjson, uvloop. langgraph 1.2.10 constraints: langchain-core<2,>=1.4.7, langgraph-checkpoint<5,>=4.1, pydantic>=2.7.4. langgraph-checkpoint-postgres 3.1.1 constraints: langgraph-checkpoint<5,>=4.1, **psycopg>=3.2, psycopg-pool>=3.2, orjson>=3.11.5**.

## Package Legitimacy Audit

> slopcheck 0.6.1 run 2026-08-04 via `uv tool install slopcheck`. All packages pre-exist in `pyproject.toml` or prior research (STACK.md) — none are new discoveries. All 22 scanned packages rated `[OK]`.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| langgraph 1.2.10 | PyPI | 2+ yrs | high (langchain org) | github.com/langchain-ai/langgraph | [OK] | Approved |
| langgraph-checkpoint-postgres 3.1.1 | PyPI | 2+ yrs | high | github.com/langchain-ai/langgraph | [OK] | Approved |
| fastapi 0.141.1 | PyPI | 7+ yrs | very high | github.com/fastapi/fastapi | [OK] | Approved |
| sqlalchemy 2.0.51 | PyPI | 19 yrs | very high | github.com/sqlalchemy/sqlalchemy | [OK] | Approved |
| alembic 1.18.5 | PyPI | 14 yrs | very high | github.com/sqlalchemy/alembic | [OK] | Approved |
| itsdangerous 2.2.0 | PyPI | 13 yrs | very high | github.com/pallets/itsdangerous | [OK] | Approved |
| pwdlib 0.3.0 | PyPI | 2 yrs | medium | github.com/frankie567/pwdlib | [OK] | Approved |
| apscheduler 3.11.3 | PyPI | 11+ yrs | high | github.com/agronholm/apscheduler | [OK] | Approved |
| redis 8.1.0 | PyPI | 13 yrs | very high | github.com/redis/redis-py | [OK] | Approved |
| httpx 0.28.1 | PyPI | 6 yrs | very high | github.com/encode/httpx | [OK] | Approved |
| tenacity 9.1.4 | PyPI | 9 yrs | high | github.com/jd/tenacity | [OK] | Approved |
| PyJWT 2.13.0 | PyPI | 10 yrs | very high | github.com/jpadilla/pyjwt | [OK] | Approved |
| pydantic-settings 2.14.2 | PyPI | 2 yrs | very high | github.com/pydantic/pydantic-settings | [OK] | Approved |
| asyncpg 0.31.0 | PyPI | 8 yrs | high | github.com/MagicStack/asyncpg | [OK] | Approved |
| supabase 2.31.0 | PyPI | 4 yrs | high | github.com/supabase/supabase-py | [OK] | Approved |
| loguru 0.7.3 | PyPI | 8 yrs | high | github.com/Delgan/loguru | [OK] | Approved |
| jinja2 3.1.6 | PyPI | 16 yrs | very high | github.com/pallets/jinja | [OK] | Approved |
| python-multipart 0.0.32 | PyPI | 10 yrs | high | github.com/Kludex/python-multipart | [OK] | Approved |
| uvicorn 0.52.1 | PyPI | 8 yrs | very high | github.com/encode/uvicorn | [OK] | Approved |
| pytest 9.1.1 / pytest-asyncio 1.4.0 | PyPI | 21/5 yrs | very high | github.com/pytest-dev/* | [OK] | Approved |
| reppy 0.4.14 (fallback only) | PyPI | 9 yrs | medium | github.com/seomoz/reppy | [OK] | Approved (fallback) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
**Transitive note:** argon2-cffi/argon2-cffi-bindings (via `pwdlib[argon2]`), psycopg/psycopg-pool (via langgraph-checkpoint-postgres), greenlet (via `sqlalchemy[asyncio]`) all have Python 3.14 wheels verified; psycopg itself is pure-Python.
**Postinstall scripts:** no Node.js packages in this phase; no suspicious install hooks observed on PyPI metadata for the listed packages.

## Architecture Patterns

### System Architecture Diagram

```
OWNER BROWSER (Phase 1 = server-rendered Jinja2, D-17)
   │  login form POST  │  queue page GET  │  approve/reject POST
   ▼                   ▼                 ▼
FASTAPI (backend/main.py) ── lifespan: init_db → alembic upgrade → scheduler start → heartbeat
   │  session auth dependency (itsdangerous cookie: HttpOnly/Secure/SameSite=Lax)
   ├─ /auth/login  /auth/logout
   ├─ /approvals (queue page)            ── reads ──┐
   ├─ /approvals/{id}: POST approve/reject/escalate ┤
   ├─ /audit?correlation_id=...          ── reads ──┐
   │                                                 ▼
   │                              ┌──────────────────────────────────────┐
   │                              │           DATA LAYER (Postgres)        │
   │                              │  audit_logs (append-only + trigger)    │
   │                              │  approval_requests (queue state)       │
   │                              │  llm_spend / outreach_spend (counters) │
   │                              │  scheduler_heartbeats                  │
   │                              │  consent_records / suppression_entries │
   │                              │  businesses, proposals, ... (existing) │
   │                              │  langgraph checkpoints (psycopg pool)  │
   │                              └────▲────────────────────────────▲──────┘
   │                                   │ writes through AuditService │
   ▼                                   │                            │
APPROVAL SERVICE: resolve row →        │                            │
  graph.stream_events(Command(resume=  │                            │
  {"decision":"approve","reason":...}),│                            │
  config={"configurable":{"thread_id": │                            │
  <approval.thread_id>}}, version="v3")│                            │
   │                                   │                            │
   ▼                                   │                            │
LANGGRAPH 1.x GRAPHS (CEO / LeadHunter / approval demo graph)
   │ nodes = thin adapters over existing BaseAgent call_llm
   ├─ llm_call node ──► BUDGET GATE (atomic counter check-and-reserve, hard block)
   │                       │                                  │
   │                       ▼                                  │
   │                 LLM PROVIDERS (OpenRouter/Groq/Gemini —  │
   │                 Gemini key now in X-Goog-Api-Key header) │
   ├─ approval node: interrupt(payload) → checkpoint saved → waits indefinitely
   └─ resume: node re-runs from top (idempotent pre-interrupt code), takes
              decision value, routes proceed/cancel, writes audit rows AFTER interrupt
   │
   ▼
APSCHEDULER (AsyncIOScheduler in lifespan)
   ├─ heartbeat job (interval): upsert heartbeat row
   ├─ sweeper job (interval): expire stale approval_requests → resume graph
   │     with Command(resume={"decision":"reject","reason":"timeout"})
   ├─ budget window reset job
   └─ listener on EVENT_JOB_ERROR → loguru alert (D-12 silent-failure alert)

FETCH PIPELINE (choke point #1 — backend/tools/http_client.py factory):
   robots cache (deny-by-default, TTL) → per-domain token bucket + jitter → httpx
SEND PIPELINE (choke point #2 — send service, Phase 3 sends; gates exist now):
   consent check → suppression check → daily volume cap → audit → send
```

### Recommended Project Structure (delta on existing tree)

```
ai-agency-os/
├── pyproject.toml              # fixed: sqlalchemy declared, langgraph 1.x, README ref OK
├── uv.lock                     # NEW — committed (D-02)
├── README.md                   # NEW — install/run instructions (D-02)
├── .gitignore                  # NEW — .env, .venv, __pycache__, etc. (CONCERNS: zero git history risk)
├── docker-compose.yml          # NEW — local Postgres (D-05)
├── alembic.ini                 # NEW
├── backend/
│   ├── __init__.py             # NEW (D-01)
│   ├── main.py                 # NEW — FastAPI app + lifespan (DB→migrate→scheduler→heartbeat)
│   ├── config.py               # extend — caps, compliance, owner creds, secret-required validation
│   ├── database.py             # repair — engine via URL.create, fail-fast, get_db guard
│   ├── models/                 # NEW — split ORM models for Alembic autogen (or keep database.py + import in env.py)
│   ├── alembic/                # NEW — env.py (async), versions/ with initial revision
│   ├── services/
│   │   ├── audit.py            # AuditService — single append-only write path
│   │   ├── approvals.py        # approval_requests CRUD + resume orchestration
│   │   ├── budget.py           # atomic cap counters (LLM + outreach)
│   │   └── compliance/         # robots.py, rate_limit.py, suppression.py, consent.py
│   ├── workflows/              # NEW — LangGraph graphs (approval demo graph, CEO, LeadHunter)
│   ├── api/                    # NEW — routers: auth, approvals, audit
│   ├── templates/              # login.html, approvals.html (Jinja2)
│   ├── agents/                 # existing — add __init__.py; base.py keeps call_llm core (Gemini header fix)
│   └── scheduler.py            # NEW — AsyncIOScheduler setup + jobs (heartbeat, sweeper)
└── tests/                      # NEW — pytest-asyncio suite (mirrors backend/)
```

### Pattern 1: LangGraph Approval Gate (interrupt + Command(resume) + approval_requests + sweeper)

**What:** Three coordinated pieces (verified against official LangGraph docs 2026-08-04):
1. **Suspension** — node calls `interrupt(payload)`; LangGraph saves a checkpoint and waits indefinitely. Payload surfaces on `stream.interrupts` (v3 streaming) or `result["__interrupt__"]` (`invoke`).
2. **Queue mirror** — before/at the gate, code inserts an `approval_requests` row (action_type, context JSON, thread_id, expires_at, status). The dashboard queries this table only — never LangGraph internals.
3. **Resume** — owner response → API resolves row → `graph.stream_events(Command(resume=payload), config={"configurable": {"thread_id": ...}}, version="v3")`. The resume value becomes `interrupt()`'s return value; the node **restarts from its beginning**.

**Hard rules (from official docs):** the same `thread_id` must be reused; any code before `interrupt()` re-runs on resume so it must be idempotent — put side effects AFTER the interrupt or in separate downstream nodes; never wrap `interrupt()` in a bare try/except; keep interrupt call order deterministic (no conditional skipping, no `while` loops — use conditional edges for re-prompting); payloads must be JSON-serializable (no functions/objects); `thread_id` < 255 chars (use UUID).

**Example (approve/reject routing — official pattern):**
```python
from typing import Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

class ApprovalState(TypedDict):
    action_details: dict
    status: Literal["pending", "approved", "rejected"]

def approval_node(state: ApprovalState) -> Command[Literal["proceed", "cancel"]]:
    decision = interrupt({"question": "Approve this action?", "details": state["action_details"]})
    return Command(goto="proceed" if decision.get("decision") == "approve" else "cancel")

def proceed_node(state: ApprovalState):  # side effects live HERE (run once after resume)
    return {"status": "approved"}

def cancel_node(state: ApprovalState):
    return {"status": "rejected"}

builder = StateGraph(ApprovalState)
builder.add_node("approval", approval_node); builder.add_node("proceed", proceed_node); builder.add_node("cancel", cancel_node)
builder.add_edge(START, "approval"); builder.add_edge("proceed", END); builder.add_edge("cancel", END)
graph = builder.compile(checkpointer=checkpointer)  # AsyncPostgresSaver in prod, InMemorySaver in tests
```
Resume from the FastAPI endpoint: `graph.stream_events(Command(resume={"decision": "approve", "reason": "ok"}), config={"configurable": {"thread_id": str(request.thread_id)}}, version="v3")`.

### Pattern 2: FastAPI Lifespan Wiring + Session Dependency

**What:** `@asynccontextmanager` lifespan (official current pattern; `on_event` is deprecated) does, in order: fail-fast config validation → DB engine/session init → `alembic upgrade head` (via `asyncio.to_thread` wrapping `command.upgrade`, since env.py runs its own `asyncio.run` in the worker thread) → `AsyncPostgresSaver` setup → scheduler start → first heartbeat → `yield` → scheduler shutdown + engine dispose.

**Session dependency:**
```python
# backend/api/deps.py
from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

serializer = URLSafeTimedSerializer(settings.session_secret, salt="owner-session")

def get_current_owner(request: Request) -> str:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = serializer.loads(token, max_age=settings.session_ttl_seconds)  # raises SignatureExpired / BadSignature
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return payload["email"]
```
Guard every dashboard route with `owner: str = Depends(get_current_owner)`. Set the cookie on login: `response.set_cookie("session", serializer.dumps({"email": settings.owner_email}), httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=settings.session_ttl_seconds)`. Password check: `PasswordHash.recommended().verify(password, settings.owner_password_hash)`.

### Pattern 3: Append-Only Audit Log

**What:** `audit_logs` table (id, actor, action, entity_type, entity_id, payload JSONB, correlation_id, created_at tz-aware). All writes flow through `AuditService.record(...)`; correlation_id threaded through graph state/AgentContext from day one (specifics: a pipeline run creates one correlation_id, every node write carries it). Immutability enforced twice: (1) no UPDATE/DELETE code paths (service exposes only `record` + `query`), (2) a PostgreSQL trigger rejecting UPDATE/DELETE on the table (defense-in-depth — a bug or admin tool cannot rewrite history). Migration includes the trigger:
```sql
CREATE OR REPLACE FUNCTION reject_audit_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_logs is append-only'; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_audit_append_only BEFORE UPDATE OR DELETE ON audit_logs
  FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();
```

### Pattern 4: Hard Budget Caps (Atomic Counters)

**What:** `llm_spend` table (provider, model, spend_date, cost_cents, calls) + `outreach_spend` (date, channel, sent_count). Enforcement is one atomic guarded UPDATE per spend event — never read-then-write (race-safe):
```sql
UPDATE llm_spend SET cost_cents = cost_cents + :cost, calls = calls + 1
WHERE provider = :provider AND model = :model AND spend_date = :today
  AND cost_cents + :cost <= :daily_cap_cents
RETURNING id;  -- rowcount 0 => hard-block
```
Blocked call → audit event (action="budget_blocked") + alert, call never reaches the provider (D-11). Same pattern for `outreach_spend` against `daily_outreach_limit`. Caps configurable in Settings (`llm_daily_budget_usd` per provider, `daily_outreach_limit` already exists).

### Pattern 5: Compliance Choke Points

**What:** (D-15) exactly two doors: the **HTTP client factory** (`backend/tools/http_client.py` — returns an httpx AsyncClient whose `fetch(url)` method always runs robots-check → rate-limit → request) and the **send service** (`compliance/check_send()` — consent exists, not suppressed, under daily cap, physical address configured). Robots: `urllib.robotparser.RobotFileParser` per domain, fetched once, TTL-cached, `can_fetch(settings.crawler_user_agent, url)` — **deny by default** on any parse failure (log + audit). Rate limit: in-process async token bucket keyed by domain (capacity + refill per second from settings, e.g., 1 req/3s default), plus uniform jitter (random sleep in `[0, period]`). Suppression: `suppression_entries` (email, reason, created_at); consent: `consent_records` (email, lawful_basis, source, granted_at, ip, user_agent). One-click unsubscribe: `GET /unsubscribe?t=<signed>` where the token is `URLSafeTimedSerializer` over the email (no DB lookup needed), which inserts a suppression entry and renders "you are unsubscribed".

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Durable suspend/resume + human approval | Custom state-machine tables + poll loops | LangGraph `interrupt()` + `AsyncPostgresSaver` | Checkpointing, crash recovery, resume semantics are the library's core; hand-rolled resume logic re-implements checkpointing badly |
| Session cookies / signed tokens | Raw HMAC, JWT-in-cookie, server session tables | itsdangerous `URLSafeTimedSerializer` | Timestamp expiry, tamper detection, key rotation, URL-safe encoding — 200 lines of crypto code you must not write |
| Password hashing | Custom hashing, SHA-256("salt"+pw), passlib | pwdlib `PasswordHash.recommended()` (Argon2id) | Argon2id parameters and verification semantics are security-sensitive; passlib is unmaintained (breaks with bcrypt>=4.1) |
| Migration versioning | `create_all` + manual ALTERs | Alembic | Schema drift is a shipped defect; autogenerate + CI check "migrations up to date" |
| Retry/backoff for LLM + HTTP | Nested sleep loops | tenacity | Retry policy (which exceptions, backoff schedule, jitter, max attempts) is precisely specified; tenacity is the standard |
| Robots.txt parsing | Regex/HTML scraping of robots.txt | `urllib.robotparser` (stdlib, D-13) | Parsing rules (wildcards, User-agent groups, Sitemap lines) have edge cases; stdlib handles them; reppy 0.4.14 is the documented hardening fallback |
| Financial amounts | `float` money | `Decimal` + `Numeric(12,2)` | Float rounding errors on money are a defect class; D-06 locked |
| Rate limiting | Per-route bolted-on middleware with global counter | Per-domain token bucket in the client factory | The requirement is per-domain (CMP-02); a global limiter gives false compliance |

**Key insight:** every "don't hand-roll" item is a trust/security surface (crypto, money, migration integrity, compliance). The pattern in this phase is: *the library owns the hard part; our code owns the policy* (caps, gate routing, audit payloads) — policy in code is exactly what D-11 demands.

## Common Pitfalls

### Pitfall 1: Side effects before `interrupt()` run twice
**What goes wrong:** DB inserts, outbox writes, or audit rows created before `interrupt()` are duplicated on every resume — the node re-runs from its start (official LangGraph behavior).
**Why it happens:** Resume semantics restart the node; code before the interrupt is re-executed.
**How to avoid:** Interrupt FIRST in the node; put all side effects after the interrupt or in downstream nodes; if pre-interrupt writes are unavoidable, make them idempotent (upserts keyed by thread_id).
**Warning signs:** duplicate audit_logs/approval_requests rows in the round-trip acceptance test.

### Pitfall 2: `interrupt()` swallowed by try/except
**What goes wrong:** The graph does not pause; the interrupt exception is caught and execution continues into code that assumes a decision exists (KeyError/None flows), or silently skips the gate entirely.
**Why it happens:** interrupt raises internally; a bare `except Exception` (this codebase already has one at `base.py:169`) catches it.
**How to avoid:** Never wrap interrupt in broad except; code-review gate for the approval node; keep the existing `except: pass` JSON-parse fix as a separate cleanup (CONCERNS).
**Warning signs:** approval_requests row created but no checkpoint/interrupt state; resume calls fail with "no pending interrupt".

### Pitfall 3: Two pools to one Postgres (asyncpg vs psycopg) — don't conflate
**What goes wrong:** Attempts to reuse the SQLAlchemy asyncpg engine as the LangGraph checkpointer (or vice versa) fail with driver errors; or checkpointer `setup()` never runs so resume fails on missing tables.
**Why it happens:** langgraph-checkpoint-postgres uses psycopg 3 + psycopg-pool, independent of SQLAlchemy; its tables (`checkpoints`, `writes`) are created only by `setup()`.
**How to avoid:** Call `await checkpointer.setup()` once in lifespan; pass a `postgresql://` DSN (not `postgresql+asyncpg://`) to `AsyncPostgresSaver.from_conn_string()`.
**Warning signs:** "relation checkpoints does not exist" on first resume; driver incompatibility errors.

### Pitfall 4: `create_all` races and stale `get_db()` TypeError persist
**What goes wrong:** Migrations not wired → `create_all` returns (single process fine, multi-process races); `get_db()` called before init raises `TypeError: 'NoneType' object is not callable`.
**Why it happens:** No migration runner in lifespan; module-level `None` globals with no guard.
**How to avoid:** Lifespan order = config validate → init_db → migrate → serve; `get_db` raises descriptive `RuntimeError("Database not initialized")` if the session maker is None; fail fast when `DATABASE_URL` missing.
**Warning signs:** CI "migrations up to date" check fails; first request 500s with TypeError.

### Pitfall 5: URL-scheme rewrite corruption + CWD-relative .env
**What goes wrong:** `database_url.replace("postgresql://", "postgresql+asyncpg://")` double-drivers already-rewritten URLs; `.env` silently skipped when launched outside repo root → placeholder owner@example.com identity and fake guardrails activate.
**Why it happens:** Naive string replace; `env_file=".env"` is CWD-relative.
**How to avoid:** Build engine with `sqlalchemy.engine.URL.create(drivername="postgresql+asyncpg", ...)` or a guard for existing driver; anchor `env_file` to `Path(__file__).resolve().parent.parent / ".env"`; make owner identity fields required (no defaults) per CONCERNS.
**Warning signs:** logs show `+asyncpg+asyncpg`; tests pass with example.com identity.

### Pitfall 6: Caps bypassed by read-then-write counters
**What goes wrong:** `SELECT spent; if spent+cost <= cap: UPDATE` races under asyncio concurrency (two calls both pass the check); or a second code path calls the provider without the budget gate.
**Why it happens:** Non-atomic counter update; multiple fetch/LLM call sites.
**How to avoid:** Single atomic `UPDATE ... WHERE spent+cost <= cap ... RETURNING` (rowcount 0 = blocked); route ALL LLM calls through `call_llm` (which contains the gate) — no new call sites; the compliance client factory is the only fetch door (D-15).
**Warning signs:** spend exceeds cap in audit export; two audit rows for one blocked call.

### Pitfall 7: Queue UI reads LangGraph internals instead of approval_requests
**What goes wrong:** Dashboard code depends on checkpoint formats; every LangGraph upgrade breaks the UI; resume targets the wrong thread.
**Why it happens:** Tempting to query `get_state()` for the queue.
**How to avoid:** approval_requests table is the ONLY queue source (D-09); thread_id stored on the row at gate time; UI renders structured context fields (amount, entity, details) — never raw LLM prose.
**Warning signs:** UI regressions after langgraph minor bump.

### Pitfall 8: Scheduler jobs doing inline work (blocks event loop)
**What goes wrong:** Heartbeat/long jobs starve the event loop; jobs lost on restart.
**Why it happens:** AsyncIOScheduler runs coroutines on the app loop; heavy I/O inline blocks everything.
**How to avoid:** D-12 enqueue-only jobs (Phase 1's real jobs are short: heartbeat upsert, sweeper resume, window reset); heavy work arrives in Phase 2 via outbox; `max_instances=1`, `misfire_grace_time` set, `coalesce=True` for sweeper jobs; EVENT_JOB_ERROR listener → alert.
**Warning signs:** request latency spikes on job tick; "misfired" warnings in logs.

### Pitfall 9: pytest-asyncio config drift (pytest 9 / pytest-asyncio 1.4)
**What goes wrong:** Async tests fail with "coroutine was never awaited" or event-loop-scope errors; unconfigured asyncio_mode forces every test to opt in.
**Why it happens:** pytest-asyncio 1.x tightened defaults; pytest 9.1.1 is newer than the declared >=7.4.
**How to avoid:** `[tool.pytest.ini_options] asyncio_mode = "auto"` + `asyncio_default_fixture_loop_scope = "function"`; run `uv run pytest` in CI.
**Warning signs:** first `uv run pytest` fails on every async test.

## Code Examples

Verified patterns from official sources:

### Approval round-trip with AsyncPostgresSaver (checkpointer setup + resume)
```python
# Source: LangGraph official persistence/checkpointers docs (docs.langchain.com/oss/python/langgraph)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = await AsyncPostgresSaver.from_conn_string(settings.database_url)  # postgresql:// (psycopg)
await checkpointer.setup()  # creates checkpoints/writes tables — REQUIRED once

config = {"configurable": {"thread_id": str(request.thread_id)}}
# First run: hits interrupt(), returns; stream.interrupted is True
stream = graph.stream_events(initial_state, config=config, version="v3")
_ = stream.output  # drain; stream.interrupts holds the payload(s)
# Owner approves:
resumed = graph.stream_events(Command(resume={"decision": "approve", "reason": "..."}), config=config, version="v3")
final_state = resumed.output  # resumes from the approval node, routes to proceed
```

### FastAPI lifespan with programmatic Alembic upgrade
```python
# Source: FastAPI official lifespan docs + Alembic cookbook (connection-sharing / command.upgrade)
from contextlib import asynccontextmanager
from alembic import command
from alembic.config import Config
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()                                   # engine + session maker (fail-fast on missing DATABASE_URL)
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "alembic"))
    await asyncio.to_thread(command.upgrade, cfg, "head")   # loop-safe: env.py runs its own asyncio.run in the thread
    await checkpointer_setup()                        # AsyncPostgresSaver.setup()
    scheduler = build_scheduler()                     # heartbeat + sweeper jobs
    scheduler.start()
    await write_heartbeat("startup")
    yield
    scheduler.shutdown(wait=False)
    await close_db()
```
Alembic env.py uses the async template: `async_engine_from_config` + `await connection.run_sync(do_run_migrations)` (alembic `init -t async`).

### AuditService append-only write
```python
# Source: pattern from research/ARCHITECTURE.md Pattern 5 (append-only decision log); API is our policy layer
class AuditService:
    async def record(self, session: AsyncSession, *, actor: str, action: str,
                     entity_type: str, entity_id: str, payload: dict, correlation_id: str) -> None:
        session.add(AuditLog(actor=actor, action=action, entity_type=entity_type,
                             entity_id=entity_id, payload=payload, correlation_id=correlation_id))
        # INSERT only — no update/delete methods exist on this service (enforced by DB trigger too)
```

### Atomic budget gate (race-safe hard block)
```python
# Source: standard guarded-UPDATE idiom; rowcount 0 == blocked
result = await session.execute(
    text("""UPDATE llm_spend SET cost_cents = cost_cents + :cost, calls = calls + 1
            WHERE provider = :provider AND model = :model AND spend_date = :today
              AND cost_cents + :cost <= :cap RETURNING id"""),
    {"cost": cost_cents, "provider": provider, "model": model, "today": date.today(), "cap": settings.llm_daily_budget_cents},
)
if result.rowcount == 0:
    await audit.record(session, actor="system", action="budget_blocked", ...)   # hard block BEFORE the call
    raise BudgetExceededError(provider, cap)
```

### Signed unsubscribe token (itsdangerous canonical use case)
```python
# Source: itsdangerous docs — "sign a user ID in a URL and email it to them to unsubscribe"
token = serializer.dumps(email)                      # URLSafeTimedSerializer(salt="unsubscribe")
# GET /unsubscribe?t=<token> →
email = serializer.loads(token, max_age=60 * 60 * 24 * 7)   # raises SignatureExpired/BadSignature
await suppression.add(session, email=email, reason="one-click-unsubscribe")
```

### httpx MockTransport for LLM client tests
```python
# Source: httpx official docs (Mock Transport)
async def handler(request: httpx.Request) -> httpx.Response:
    assert request.url.host == "openrouter.ai"
    return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})

transport = httpx.MockTransport(handler)
async with httpx.AsyncClient(transport=transport, base_url="https://openrouter.ai") as client:
    ...
```
`BaseAgent.call_llm` must accept an injected client (or the transport) so tests never hit the network.

### In-process per-domain token bucket with jitter
```python
# Source: standard token-bucket idiom (research/ARCHITECTURE.md Pattern 4); policy numbers from Settings
class DomainTokenBucket:
    def __init__(self, capacity: float, refill_per_sec: float):
        self.capacity, self.refill = capacity, refill_per_sec
        self.tokens: dict[str, float] = {}; self.last: dict[str, float] = {}
    async def acquire(self, domain: str) -> None:
        now = time.monotonic()
        self.tokens[domain] = min(self.capacity,
            self.tokens.get(domain, self.capacity) + (now - self.last.get(domain, now)) * self.refill)
        self.last[domain] = now
        if self.tokens[domain] < 1:
            wait = (1 - self.tokens[domain]) / self.refill
            await asyncio.sleep(wait + random.uniform(0, 1 / self.refill))   # jitter per CMP-02
            self.tokens[domain] = 0
        else:
            self.tokens[domain] -= 1
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| langgraph 0.0.x (declared pin) | LangGraph 1.x `interrupt()`/`Command`/`PostgresSaver` | 1.0 (late 2024) | Complete API rewrite; old pin is unusable; HITL is now first-class |
| `Base.metadata.create_all` | Alembic migrations | This phase | Schema drift eliminated; CI can verify "up to date" |
| passlib (bcrypt) | pwdlib `PasswordHash.recommended()` (Argon2id) | passlib unmaintained since 2020; breaks on bcrypt>=4.1 | Modern default algorithm; maintained library |
| python-jose | PyJWT | python-jose slow/CVE history | Maintained standard (D-03; latent until tokens are issued) |
| `datetime.utcnow` | `datetime.now(timezone.utc)` | deprecated 3.12 | tz-aware timestamps everywhere (D-07) |
| float money | Decimal/Numeric(12,2) | This phase (D-06) | Financial precision; audit-grade amounts |
| pytest 7.x (declared) | pytest 9.1.1 + pytest-asyncio 1.4.0 | 2025-2026 | Current majors; asyncio_mode config |

**Deprecated/outdated:**
- FastAPI `@app.on_event("startup"/"shutdown")`: deprecated — use lifespan (official docs verified).
- `urllib.robotparser` (D-13 lock): stdlib, fine for v1; reppy 0.4.14 is the documented hardening path if real-world robots.txt breaks parsing.
- APScheduler 4.x: alpha — pin `<4`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | tenacity 9.1.4 addition for LLM retry (beyond D-03's locked list) | Standard Stack | Low — retry/backoff is mandated by CONCERNS + research SUMMARY; if planner defers it, the 60s-no-retry defect stays in call_llm |
| A2 | In-process token bucket instead of Redis-backed limiter | Architecture Patterns | Low at single-instance scale; if the owner later runs multiple workers, per-domain limits are per-process (need Redis counters then) |
| A3 | PostgreSQL trigger as the audit immutability guarantee | Architecture Patterns | Low — pure defense-in-depth on top of no-UPDATE/DELETE code paths; if the DB user lacks TRIGGER privileges on Supabase, application-level enforcement alone remains (flag in verification) |
| A4 | pytest 9.1.1 / pytest-asyncio 1.4.0 as dev versions (STACK.md said pytest>=8) | Standard Stack | Low — verified current on PyPI; pytest-asyncio 1.x config keys verified pattern |
| A5 | Session TTL/cookie-secure defaults (e.g., 12h TTL, Secure flag behind settings) | Patterns | Low — planner discretion; D-16 locks flags (HttpOnly/Secure/SameSite) not durations |
| A6 | `audit_logs` table name (research used `decision_events`) | Patterns | Negligible — file naming is planner discretion; column shape per D-07 is locked |
| A7 | PyJWT kept declared but unused in Phase 1 (itsdangerous covers session + unsubscribe) | Standard Stack | Negligible — D-03 locks the dependency; if it must be used, unsubscribe tokens can switch to PyJWT with no schema change |

## Open Questions (RESOLVED)

1. **Owner credentials storage** (D-16 "seeded from env config")
   - What we know: single owner; pwdlib argon2 hash needed at startup.
   - What's unclear: whether the hash lives in `.env` (`OWNER_PASSWORD_HASH` — pre-computed) or the app hashes a plaintext `OWNER_PASSWORD` env var at first boot.
   - Recommendation: hash stored in env (`OWNER_PASSWORD_HASH`), generated by a `scripts/hash_password.py` utility; plaintext password never in env. Planner picks; hash-in-env is safer.
   - **RESOLVED (plan 01-01 Task 3):** hash-in-env chosen — `scripts/hash_password.py` (Argon2id via pwdlib) generates OWNER_PASSWORD_HASH; plaintext password never in env (D-16).

2. **When exactly does `alembic upgrade head` run?**
   - What we know: D-05 allows startup-run or documented explicit step.
   - What's unclear: startup auto-migration is convenient for the owner (success criterion 1) but runs DDL on every boot; multi-worker races.
   - Recommendation: lifespan `asyncio.to_thread(command.upgrade, ...)` for dev convenience + README documents `alembic upgrade head`; CI runs it against an ephemeral Postgres in the installability job. Single-process deployment makes startup-run safe.
   - **RESOLVED (plan 01-01 Task 2b):** startup-run via lifespan `asyncio.to_thread(command.upgrade, cfg, "head")` (single-process dev) + README documents the manual step; CI smoke job runs `alembic upgrade head` against an ephemeral Postgres (SC1 gate).

3. **What does the CEO/LeadHunter round-trip graph actually DO in Phase 1?**
   - What we know: must prove approve→resume→complete and reject→halt with the existing agents (success criterion 3); discovery is Phase 2 so real lead collection is out.
   - What's unclear: the concrete state flow (LeadHunter "discover" mock-gated by MOCK_MODE → CEO proposal review node → interrupt gate → proceed/cancel).
   - Recommendation: a `ceo_review` workflow: lead_hunter node (MOCK_MODE-gated mock leads or empty result) → ceo proposal node (evidence fields, D-10) → approval gate (always interrupt for the demo path via a test fixture action) → finalize node. The acceptance test drives it without any network/LLM (httpx MockTransport or a fake provider).
   - **RESOLVED (plan 01-03):** `ceo_review` workflow — discover (MOCK_MODE-gated, D-20) → propose (evidence fields, D-10) → prepare_request → gate (interrupt) → proceed/cancel; acceptance test runs on httpx MockTransport + AsyncPostgresSaver against the test DB, no network/LLM.

4. **Outbox table in Phase 1?**
   - What we know: D-12 mandates enqueue-only jobs; heavy jobs arrive Phase 2; research places the outbox worker in Phase 2.
   - What's unclear: whether the outbox_events table is created now (schema) with the worker deferred, or entirely deferred.
   - Recommendation: defer the outbox table/worker entirely to Phase 2 — Phase 1 scheduler jobs (heartbeat, sweeper, window reset) are short and inline-safe; create the table when the first heavy job needs it. Flagged so the planner doesn't build half an outbox.
   - **RESOLVED (planner decision, honored across all plans):** outbox_events table + worker deferred entirely to Phase 2 (D-12) — no Phase 1 plan creates it; Phase 1 scheduler jobs (heartbeat, approval sweeper, budget window reset) run inline via APScheduler.

5. **Redis in Phase 1?**
   - What we know: redis 8.1.0 stays declared (D-03); local Redis is absent.
   - What's unclear: any Redis usage this phase (rate limits, cache)?
   - Recommendation: none — in-process bucket + atomic SQL counters; document the Redis-backed swap path for multi-process deployment.
   - **RESOLVED (plan 01-05):** no Redis usage in Phase 1 — in-process `DomainTokenBucket` (per-domain, with jitter) + atomic SQL counters (`reserve_outreach`); Redis-backed swap path documented for multi-process deployment (Assumption A2).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | runtime (dev machine) | ✓ | 3.14.5 | — (all binary wheels verified for cp314) |
| uv | lockfile + installs (D-02) | ✓ | 0.9.27 | — |
| PostgreSQL | all DB features (FND-03..06) | ⚠ installed, **not running** | 15.18 (Homebrew) | `docker compose up -d` (Docker 28.5.1 ✓) or `brew services start postgresql@15` — **planner must add a setup task** |
| Docker | docker-compose Postgres (D-05) | ✓ | 28.5.1 | — |
| Redis | rate-limit counters (optional) | ✗ | — | in-process token bucket (chosen; A2) |
| LLM provider keys | agent round-trip demo | ✗ (no .env present) | — | httpx MockTransport / fake provider in tests; MOCK_MODE gate (D-20) |
| Network to PyPI | dependency install | ✓ | — | — |
| slopcheck | package audit | ✓ (installed this session) | 0.6.1 | — |

**Missing dependencies with no fallback:**
- Postgres must be running (any local route) — the only true blocker; address in Wave 0/1 as a setup task (docker-compose file is itself a Phase 1 deliverable, so first use the existing Homebrew install or write the compose file early).
- No LLM keys / `.env` — expected; all agent tests use MockTransport; the round-trip acceptance test must not require live providers.

**Missing dependencies with fallback:** Redis → in-process bucket; live LLM → mocked transport (D-19 explicitly tests "LLM client error paths" without network).

## Validation Architecture

> `workflow.nyquist_validation: true` in `.planning/config.json` — section required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (dev extras; `uv run pytest`) |
| Config file | `[tool.pytest.ini_options]` in pyproject.toml: `asyncio_mode = "auto"`, `asyncio_default_fixture_loop_scope = "function"`, `testpaths = ["tests"]` |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest` (plus CI: `ruff` → `black --check` → `mypy` → `pytest`, D-19) |
| Test DB | Real PostgreSQL (models use PGUUID → SQLite incompatible): dedicated database `ai_agency_os_test` on the local instance (docker-compose or Homebrew); tests create schema via Alembic upgrade head, not create_all |
| LangGraph test checkpointer | `InMemorySaver` (langgraph.checkpoint.memory) for unit tests; `AsyncPostgresSaver` against the test DB for the round-trip integration test (verify checkpoint → interrupt → resume durability) |
| LLM tests | `httpx.MockTransport` injected into `BaseAgent.call_llm` — zero network in tests |

### Success Criteria → Validation Map

| Success Criterion | Behavior | Test Type | Automated Command | File Exists? |
|-------------------|----------|-----------|-------------------|-------------|
| SC1 — installable package, current deps, uv.lock, alembic upgrade | `uv sync --frozen` from lockfile; `pip install -e .` in fresh venv; `alembic upgrade head` against empty DB; `/health` responds | CI smoke (GitHub Actions job) + pytest fixture | CI job: fresh venv → `pip install -e .` → `alembic upgrade head` → `uvicorn` smoke → `uv run pytest` | ❌ Wave 0 (CI config + smoke script) |
| SC2 — session auth + append-only audit queryable by correlation_id | login sets cookie; protected routes 401 without it; AuditService writes rows; query by correlation_id returns the trail; UPDATE/DELETE on audit_logs raises | unit + integration | `uv run pytest tests/test_auth.py tests/test_audit.py -x -q` | ❌ Wave 0 |
| SC3 — approval round-trip with CEO/LeadHunter agents | graph runs → interrupts at gate → approval_requests row PENDING → POST approve resumes to final state; POST reject halts; queue page renders the gated details | integration (PostgresSaver + TestClient) — **the capstone acceptance test** | `uv run pytest tests/test_approval_roundtrip.py -x -q` | ❌ Wave 0 |
| SC4 — caps hard-block; scheduler heartbeats + alert | LLM call at cap → BudgetExceededError + audit row, provider never called; concurrent overspend blocked; heartbeat row written; staleness function flags missed beats; job error listener fires | unit (atomicity via concurrent tasks) | `uv run pytest tests/test_budget.py tests/test_scheduler.py -x -q` | ❌ Wave 0 |
| SC5 — robots deny-by-default, per-domain rate limit + jitter, suppression/consent, unsubscribe | robots deny blocks fetch; parse failure denies; bucket limits per domain (N requests in window); suppressed/consented-absent send is blocked at the send gate; unsubscribe endpoint inserts suppression and blocks next send | unit + API integration | `uv run pytest tests/test_compliance.py -x -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q` (fast subset; unit-level)
- **Per wave merge:** `uv run pytest` (full suite)
- **Phase gate:** full suite green + CI smoke (fresh-venv install + migrations) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` — shared fixtures: settings with test env (`get_settings.cache_clear()` + env patch, per CONCERNS), async engine/session for `ai_agency_os_test`, Alembic upgrade fixture, InMemorySaver + AsyncPostgresSaver fixtures, MockTransport handler factory
- [ ] `tests/test_config.py` — config validation: required identity fields fail fast, alias mapping, placeholder rejection
- [ ] `tests/test_database.py` — DB lifecycle: get_db before init raises RuntimeError, URL creation with existing driver, tz-aware defaults, callable JSON defaults
- [ ] `tests/test_audit.py` — append-only service + trigger tamper test
- [ ] `tests/test_auth.py` — login/logout, cookie flags, expiry, tampered cookie 401
- [ ] `tests/test_budget.py` — cap math, atomicity under concurrency, breach audit
- [ ] `tests/test_scheduler.py` — heartbeat write + staleness detection + job-error listener
- [ ] `tests/test_compliance.py` — robots (allow/deny/parse-failure), token bucket + jitter, suppression/consent gates, unsubscribe
- [ ] `tests/test_approval_roundtrip.py` — SC3 capstone (graph + PostgresSaver + TestClient approve/reject/escalate)
- [ ] `tests/test_llm_client.py` — provider request building (Gemini key in header!), error paths, retry behavior
- [ ] Framework install: dev extras (`pytest`, `pytest-asyncio`, `pytest-cov`) via `uv add --dev`
- [ ] Postgres test database setup task (Wave 0/1): create `ai_agency_os_test`, run migrations in fixture

## Security Domain

> `security_enforcement: true` (absent = enabled); ASVS level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | pwdlib[argon2] `PasswordHash.recommended()` verify; owner from env; constant-time verify via argon2; login rate-limit (minimal, e.g., per-IP delay) |
| V3 Session Management | yes | itsdangerous `URLSafeTimedSerializer` signed cookie: HttpOnly + Secure + SameSite=Lax, max_age TTL, re-issue on login, delete on logout |
| V4 Access Control | yes | single-owner: `Depends(get_current_owner)` guard on every dashboard/queue/audit route; no public write endpoints except unsubscribe (token-gated) |
| V5 Input Validation | yes | pydantic request/response models; SQLAlchemy parameterized queries (no f-string SQL); email validation via pydantic EmailStr or email-validator |
| V6 Cryptography | yes | No hand-rolled crypto anywhere: itsdangerous HMAC signing, argon2id hashing, `secrets.token_*` for any random tokens; secrets in env, never in code |

### Known Threat Patterns for Phase 1 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Session cookie theft (XSS/network) | Information Disclosure | HttpOnly + Secure flags; SameSite=Lax; loguru redaction of cookies/tokens in sinks (D-18) |
| CSRF on state-changing routes | Spoofing | SameSite=Lax blocks cross-site POST cookies; same-origin SSR UI only; optional Origin header check on approve/reject endpoints (cheap, add it) |
| Audit log tampering (post-hoc rewrite of AI decisions) | Tampering | Append-only service + PostgreSQL trigger rejecting UPDATE/DELETE (Pattern 3); correlation_id trails; no delete endpoints |
| Budget cap bypass (race or alternate path) | Tampering/Elevation | Atomic guarded UPDATE (rowcount check); single LLM door (`call_llm`) and single fetch door (client factory); breach → audit + alert (D-11, D-15) |
| Prompt injection into approval-gate decisions | Tampering | Gate payloads are structured state (amount, entity_type, details from business objects) built by code — never LLM free text; queue UI renders fields, not raw prose; LLM output never sets the decision value |
| Gemini key leakage via URL | Information Disclosure | `X-Goog-Api-Key` header (D-18); loguru redaction of `*key*`, `*token*`, `*secret*` fields |
| Timing attacks on login | Information Disclosure | argon2 verify is intrinsically slow/constant-ish; uniform error message ("invalid credentials") for wrong email vs wrong password |
| Checkpoint/state poisoning (thread_id guessability) | Spoofing | thread_id = UUID stored on approval_requests row; resume only via that row; never accept client-supplied thread_id without a matching pending request |

## Sources

### Primary (HIGH confidence)
- LangGraph official docs (docs.langchain.com/oss/python/langgraph) — interrupts (`interrupt()`/`Command(resume=...)`, node-restart-on-resume, interrupt rules), persistence, checkpointers (`AsyncPostgresSaver`, `setup()`, thread_id limits, durability modes, get_state/update_state) — fetched 2026-08-04
- PyPI JSON API (pypi.org/pypi/<pkg>/json) — all 24 versions verified 2026-08-04; dependency constraints (langgraph→langchain-core<2,>=1.4.7; langgraph-checkpoint-postgres→psycopg>=3.2, psycopg-pool, orjson); cp314/cp39-abi3 wheel availability for asyncpg, greenlet, psycopg-binary, argon2-cffi-bindings, bcrypt, cffi, orjson, uvloop
- FastAPI official docs (fastapi.tiangolo.com/advanced/events) — lifespan asynccontextmanager (on_event deprecated)
- Alembic official docs (alembic.sqlalchemy.org/en/latest/cookbook.html) — programmatic `command.upgrade`, connection sharing via `Config.attributes`, async env pattern
- itsdangerous official docs (itsdangerous.palletsprojects.com) — serializer/signer/timed/URL-safe APIs; unsubscribe-link canonical use case
- APScheduler official docs (apscheduler.readthedocs.io/en/3.x) — AsyncIOScheduler, triggers, misfire/coalescing, add_listener events, job persistence rules
- pwdlib README (github.com/frankie567/pwdlib) — `PasswordHash.recommended()` hash/verify API
- slopcheck 0.6.1 scan output — 22/22 packages [OK]
- Existing project research (.planning/research/SUMMARY.md, STACK.md, ARCHITECTURE.md, PITFALLS.md) and codebase maps (.planning/codebase/) — as-built ground truth

### Secondary (MEDIUM confidence)
- httpx MockTransport testing pattern (httpx official docs) — standard seam for LLM client tests
- pytest-asyncio 1.x config keys (asyncio_mode / loop scope) — official docs; verified against installed version constraints
- urllib.robotparser stdlib behavior (Python docs) — parsing rules for robots.txt (D-13 lock)

### Tertiary (LOW confidence)
- None critical to this phase's decisions; open questions (owner-credential storage, outbox timing) are policy choices for the planner, not unverifiable facts.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified on PyPI JSON API today; wheel compatibility for Python 3.14.5 verified per-package; 22/22 slopcheck OK
- Architecture: HIGH — LangGraph interrupt/resume/checkpoint semantics from official docs; FastAPI lifespan and Alembic patterns from official docs; compliance patterns from prior research (D-13..D-15 locked)
- Pitfalls: MEDIUM-HIGH — interrupt-restart and driver-separation pitfalls are doc-verified; scheduler/heartbeat and token-bucket operational details are ecosystem-consensus (MEDIUM)

**Research date:** 2026-08-04
**Valid until:** 2026-09-03 (30 days — stack pins are verified-current today; langgraph minor releases move fast, lockfile protects us)
