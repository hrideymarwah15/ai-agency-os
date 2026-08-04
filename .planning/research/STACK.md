# Stack Research

**Domain:** Autonomous AI-powered digital agency platform (AI Agency OS) — multi-agent orchestration, web intelligence/crawling, sales automation, document generation, payments, owner dashboard
**Researched:** 2026-08-04
**Confidence:** HIGH for versions (verified against PyPI/npm registries today); MEDIUM for qualitative ecosystem-fit claims

## Declared Stack Verdict (what's current vs outdated)

All versions below verified against `pypi.org/pypi/<pkg>/json` and `registry.npmjs.org/<pkg>/latest` on 2026-08-04. The declared stack is *directionally correct* (FastAPI + async SQLAlchemy/Supabase + Redis + httpx + LangGraph + Playwright + Next.js/Tailwind is the right family for this product) but **every pin is 1–3 years stale, and three choices are actively wrong**.

| Declared | Pin in pyproject | Current (verified) | Verdict |
|---|---|---|---|
| Python | >=3.11 | 3.11 EOL 2027-10; dev runs 3.14.5 | **KEEP** >=3.11 floor; test on 3.13/3.14. LangGraph 1.x needs >=3.10, asyncpg 0.31 fine |
| FastAPI | >=0.109.0 (Jan 2024) | **0.141.1** | **BUMP** — 12 minors behind; still the right framework |
| uvicorn | >=0.27.0 | **0.52.1** | BUMP |
| pydantic / pydantic-settings | >=2.5.0 / >=2.1.0 | **2.13.4 / 2.14.2** | BUMP |
| SQLAlchemy async | **MISSING** (used in `backend/database.py`) | **2.0.51** | **CRITICAL GAP — ADD** `sqlalchemy[asyncio]>=2.0.51` |
| Alembic | **MISSING** (CONCERNS requires migrations) | **1.18.5** | **CRITICAL GAP — ADD**; replace `create_all` |
| supabase | >=2.3.0 | **2.31.0** | BUMP; keep client for auth/storage/realtime — DB access stays SQLAlchemy |
| asyncpg | >=0.29.0 | **0.31.0** | BUMP |
| redis (redis-py) | >=5.0.0 | **8.1.0** | **BUMP 3 majors** — 6/7/8 released since; async client API stable |
| httpx | >=0.26.0 | **0.28.1** | BUMP |
| **langgraph** | **>=0.0.30 (early 2024)** | **1.2.10** | **CRITICAL — API completely rewritten.** 0.0.x code will not port. Treat as new adoption at >=1.2 |
| langchain-core / langchain-openai | >=0.1.0 / >=0.0.8 | 1.5.3 / 1.4.1 | **REMOVE explicit pins** — langgraph 1.x pulls `langchain-core<2,>=1.4.7` transitively. Keep langchain-openai only if adopting its model clients (not required) |
| openai | >=1.12.0 | **2.53.0** | BUMP only if/when using OpenAI-compatible tool-calling via the SDK; raw httpx covers current needs |
| playwright | >=1.40.0 | **1.62.0** | BUMP; requires `playwright install chromium` (undocumented in repo) |
| stripe | >=7.0.0 | **15.4.0** | **BUMP 8 majors** — v7 API is dead code waiting to happen. Do in finance phase |
| razorpay | >=1.4.0 | **2.0.1** | **BUMP to v2** — v2 has a new client API; 1.x code won't port |
| sendgrid | >=6.10.0 | 6.12.5 | Fine (minor bump) |
| apscheduler | >=3.10.0 | **3.11.3** | Keep. **Do NOT use 4.x** — still alpha (4.0.0a6) |
| jinja2 | >=3.1.0 | 3.1.6 | Fine |
| python-multipart | >=0.0.6 | 0.0.32 | BUMP (needed once forms/uploads land) |
| python-jose | >=3.3.0 | 3.5.0 | **REPLACE with PyJWT 2.13.0** — python-jose is the ecosystem's deprecated path (slow releases, CVE history); PyJWT is the standard |
| passlib | >=1.7.4 | 1.7.4 (stale since 2020) | **REPLACE with pwdlib 0.3.0** (or direct bcrypt 5.0.0) — passlib breaks with bcrypt>=4.1 (`__about__` error) |
| python-dotenv | >=1.0.0 | 1.2.2 | **REMOVE** — redundant; pydantic-settings loads `.env` itself |
| loguru | >=0.7.0 | 0.7.3 | Fine |
| Lockfile | **NONE** | — | **CRITICAL GAP — ADD** `uv.lock` via uv |
| Next.js (planned) | 14 | **16.3.0** | **BUMP 2 majors** — Next 14 is 2 majors behind; Next 16 is current stable (15 was the interim) |
| React (planned) | 18 | **19.2.8** | **BUMP** — Next 16 requires React 19 |
| Tailwind (planned) | v4 | **4.3.3** | **CORRECT** — v4 is current; use `@tailwindcss/postcss` (CSS-first config, no `tailwind.config.js` needed) |

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | >=3.11 (test 3.13/3.14) | Backend language | Declared; entire skeleton is Python. LangGraph 1.x requires >=3.10, so the floor is safe |
| FastAPI | 0.141.1 | API gateway, webhooks (Stripe/Razorpay/WhatsApp), owner dashboard backend | The standard async Python API framework; native lifespan wiring for `init_db`/`close_db`; built on pydantic 2.13. Zero reason to change |
| SQLAlchemy | 2.0.51 (`sqlalchemy[asyncio]`) | ORM over Supabase-hosted Postgres | Already the as-built ORM (`backend/database.py`); 2.0 async is the Python standard. **Must be declared** — it's imported today with no dependency entry |
| Alembic | 1.18.5 | DB migrations | The standard migration tool for SQLAlchemy; CONCERNS explicitly flags `create_all` as un-versionable. Ships with SQLAlchemy support for async engines via `asyncpg`-style env config |
| Supabase (Postgres + pgvector) | 2.31.0 client / managed PG | Primary store + embeddings | Declared and correct: managed Postgres (free tier), pgvector for the planned embedding/vector features, client SDK for auth/storage/realtime. Postgres is the right store for lead scoring, finance, and audit-log (append-only) workloads |
| pgvector | 0.5.0 (Python) | Vector column support + client | SPEC-001/002 plan embeddings for enrichment/dedup; SQLAlchemy-native column type |
| Redis (redis-py) | 8.1.0 | Rate-limit counters, LLM response cache, queue (v1: Redis Streams), scheduler state | Declared; current major. Async client (`redis.asyncio`) is stable. **Do NOT pin redis<6 for arq** (see What NOT to Use) |
| httpx | 0.28.1 | LLM provider transport (OpenRouter/Groq/Gemini/Ollama) + crawling | Already the implemented transport in `BaseAgent.call_llm`; async, free-tier friendly, provider-agnostic. **Keep raw httpx — do not force LangChain model clients** |
| LangGraph | 1.2.10 | Agent orchestration: department state machines, durable execution, human-approval gates | The 2025-2026 standard for durable multi-agent workflows. Verified via official docs: `interrupt()`/`Command(resume=...)` gives first-class **human-in-the-loop** (pause → owner approves/rejects → resume from same node) — exactly the contract/payment approval gates this product requires. Nodes are plain Python callables, so existing `BaseAgent.call_llm` wraps directly — no langchain client migration needed |
| langgraph-checkpoint-postgres | 3.1.1 | Durable execution — graph state survives restarts/worker crashes | LangGraph 1.x checkpointing over the existing Supabase Postgres; this is what makes "autonomous operation" resumable and auditable (correlation with SPEC-001 MessageEnvelope/AuditEntry) |
| Playwright | 1.62.0 | Browser rendering for site audits (Lighthouse-style perf/SEO/UX scoring), tech detection harvesting, PDF generation | Declared and still the standard browser-automation tool. Async API fits the stack. Use in-process with a semaphore at v1 volumes (5–10 audits/day); move to worker processes if crawl scale grows |
| APScheduler | 3.11.3 (`<4`) | Cron-style daily cycle: lead discovery, outreach, maintenance checks | Declared; the standard in-process scheduler for single-instance deployments. 4.x is alpha — pin `<4`. Job handlers enqueue to Redis; scheduler itself stays in-process |
| Jinja2 | 3.1.6 | Proposal/contract/invoice/email templates | Declared; already scaffolded in `backend/templates/`. The standard Python templating for documents |
| WeasyPrint | 69.0 | HTML → print-quality PDF (proposals, contracts, invoices) | The standard Python HTML→PDF renderer (no Node dependency, deterministic). Alternative: Playwright `page.pdf()` — both valid; pick one in the docs phase. See Alternatives |
| Stripe | 15.4.0 | Recurring billing, subscriptions, webhooks | Declared direction correct; **bump from v7 in the finance phase** — v7 API surface is 8 majors stale |
| Razorpay | 2.0.1 | INR payments, subscriptions, webhooks | Declared direction correct; **bump to v2** — v1.4 client API is replaced |
| SendGrid | 6.12.5 | Transactional/outreach email (with SMTP fallback) | Declared; free tier fits budget; SMTP fallback already configured in `config.py` |
| PyJWT | 2.13.0 | Auth tokens for owner dashboard/API | Standard, actively maintained JWT lib. Replaces python-jose (declared but wrong choice in 2026) |
| pwdlib | 0.3.0 | Password hashing | Modern replacement for stale passlib (FastAPI-docs-adjacent ecosystem); argon2/bcrypt backends. Alternative: direct bcrypt 5.0.0 |
| Next.js | 16.3.0 | Owner dashboard + client portal (App Router, Server Components) | Current stable; the standard React framework for dashboards needing auth, API routes, and future client-facing pages. Declared Next 14 is outdated — plan for Next 16 (React 19 required) |
| React | 19.2.8 | Frontend runtime | Required by Next 16; current stable |
| Tailwind CSS | 4.3.3 (+ `@tailwindcss/postcss`) | Styling | Declared v4 is correct and current; CSS-first config |
| shadcn/ui | 4.16.1 (CLI) | Dashboard component library | The 2026 standard for Next.js dashboards (tables, dialogs, sheets, forms, sidebars) — copy-in components, no license issues |
| Recharts | 3.10.1 | MRR/ARR, pipeline, margin charts | Standard React charting; fine for finance dashboard |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | 9.1.4 | Retry/backoff for LLM calls + crawler fetches | Foundation phase — CONCERNS flags 60s-no-retry as a real defect; retry 429/5xx with exponential backoff |
| httpx-sse | 0.4.3 | SSE streaming from OpenRouter (token streaming to dashboard) | When streaming agent output to the dashboard lands |
| email-validator | 2.3.0 | Email validation in pydantic models + lead enrichment | Foundation; prevents garbage outreach addresses |
| orjson | 3.11.9 | Fast JSON (pydantic `model_dump_json` / response serialization) | Optional perf; add if profiling shows serialization cost |
| sentry-sdk | 2.66.1 | Error tracking | DSN already configured in `config.py` but SDK never declared — add in foundation |
| wappalyzer | 2.0.2 | Tech-stack detection (CMS, analytics, hosting) from HTML/headers | Website-intelligence phase. Free local patterns. **MEDIUM confidence** — small project, verify maintenance when adopting; keep a regex fallback |
| reppy | 0.4.14 | Robust robots.txt parsing/caching | Crawler phase — compliance requirement (SPEC-002 robots.txt respect). `urllib.robotparser` is too naive for real-world robots.txt |
| slowapi | 0.1.10 | FastAPI rate limiting (per-route/global) | Foundation — SPEC-002 rate-limit compliance; also protects webhook endpoints. Or hand-roll with Redis counters (MEDIUM: slowapi maintenance is sporadic; simple Redis-counter middleware may be more robust) |
| num2words | 0.5.14 | INR amount-in-words on invoices (legal requirement in India) | Finance/document phase |
| Babel | 2.18.0 | INR formatting (`₹1,25,000`), locale-aware dates | Document/finance phase |
| python-docx | 1.2.0 | Editable DOCX generation (proposals clients can edit) | Only if clients need editable docs; PDF-first otherwise |
| langgraph-sdk | 0.4.2 | HTTP API to LangGraph Platform-style runtime | Only if deploying graphs as a separate runtime; **not needed for v1** (run graphs in-process) |
| sqlalchemy-utils / greenlet | (transitive via `sqlalchemy[asyncio]`) | Async ORM runtime requirement | Declare `sqlalchemy[asyncio]` extra so greenlet resolves explicitly |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** | Dependency management + lockfile + venv | **CRITICAL ADD** — no lockfile exists today; `>=`-only pins mean every install resolves differently. `uv lock` produces `uv.lock`; `uv` is the 2025-2026 standard (replaces pip/poetry for new work). Keep setuptools build backend |
| pytest + pytest-asyncio + pytest-cov | Tests | Declared; bump pytest to current major (>=8). Add `asyncio_mode = "auto"` config |
| ruff / black / mypy | Lint/format/types | Declared and configured (line-length 100, py311). Keep — they're current |
| `playwright install chromium` | Browser binaries | Undocumented in repo — add to foundation-phase docs/setup |
| Alembic `alembic init` + CI check | Migrations | CONCERNS-mandated; CI gate "migrations up to date" |
| GitHub Actions | CI (lint → typecheck → test) | None exists; zero-commit repo. First commit must ship `.gitignore` + CI |

## Installation

```bash
# Backend (uv — generates uv.lock; replaces bare pip)
uv add "fastapi>=0.141" "uvicorn[standard]>=0.52" "pydantic>=2.13" "pydantic-settings>=2.14"
uv add "sqlalchemy[asyncio]>=2.0.51" "asyncpg>=0.31" "alembic>=1.18" "pgvector>=0.5" "supabase>=2.31"
uv add "redis>=8.1" "httpx>=0.28" "tenacity>=9.1" "httpx-sse>=0.4"
uv add "langgraph>=1.2" "langgraph-checkpoint-postgres>=3.1"
uv add "playwright>=1.62" "reppy>=0.4" "wappalyzer>=2.0"
uv add "jinja2>=3.1" "weasyprint>=69" "python-docx>=1.2" "num2words>=0.5" "babel>=2.18"
uv add "stripe>=15.4" "razorpay>=2.0" "sendgrid>=6.12"
uv add "apscheduler>=3.11,<4" "loguru>=0.7" "python-multipart>=0.0.32"
uv add "pyjwt>=2.13" "pwdlib>=0.3" "email-validator>=2.3" "sentry-sdk>=2.66"
uv add --dev "pytest>=8" "pytest-asyncio" "pytest-cov" "ruff" "mypy"
uv lock
uv run playwright install chromium

# Frontend (Next 16 + React 19 + Tailwind v4 + shadcn/ui)
npx create-next-app@latest frontend --app --ts --tailwind --eslint
npm i recharts
npx shadcn@latest init
npx shadcn@latest add button card table dialog sheet sidebar tabs form select badge
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| LangGraph 1.x | **pydantic-ai 2.23.0** | If orchestration stays mostly single-agent loops with tools; pydantic-ai is excellent for typed structured output but its multi-agent/durable-state story is younger than LangGraph 1.x durable execution. Revisit per-department if a department never needs resume/approval |
| LangGraph 1.x | **CrewAI 1.15.10** | Only if you want batteries-included crews and can accept less explicit control over state — the approval-gate requirements (SPEC-001 ApprovalRequest, resume-after-human-input) are state-machine problems; LangGraph's `interrupt` is purpose-built for them |
| LangGraph 1.x | **OpenAI Agents SDK 0.19.3** | If you standardized on OpenAI/OpenRouter exclusively and never need Postgres checkpointing. The project's provider-agnostic fallback chain (OpenRouter→Groq→Gemini→Ollama) fits LangGraph's model-agnostic nodes better |
| LangGraph 1.x | Hand-rolled state machine (postgres tables + APScheduler) | If the graph stays under ~5 agents with no resume requirement. LangGraph's value = durable resume + built-in audit of graph state for free |
| LangGraph 1.x | Temporal | If you need heavyweight durability guarantees (retries, timers, visibility) at infra cost. Overkill for a single-tenant platform |
| Playwright | **Crawlee 1.9.0 (Python)** | If crawl volume/compliance rigor grows: built-in robots.txt, rate limiting, fingerprint rotation, proxy support. At 10 leads/day v1, Playwright + reppy + own limiter is simpler |
| Playwright | **crawl4ai 0.9.2** | If the crawler's main job becomes LLM-friendly content extraction (markdown, structured) rather than metrics/tech-detection. crawl4ai is young (0.x) — watch API churn |
| WeasyPrint 69 | Playwright `page.pdf()` | Playwright is already in the stack (zero new deps) and has modern CSS support; WeasyPrint is deterministic and lighter at runtime. Either works — decide in the docs phase; don't add both |
| Next.js 16 | Next.js 15 | Only if a critical plugin still lags 16. Next 16 is current stable; 14 (declared) is 2 majors behind |
| Next.js 16 | Vite + React SPA | If the dashboard needs zero SEO and you want a lighter build. Next is the standard, and the client portal/landing pages planned later want SSR/SEO |
| redis-py 8.1 | arq 0.28 + redis-py 5.3.1 | If you want a batteries-included async job framework *and* accept pinning redis-py back to 5.x (arq requires `redis<6`) — see What NOT to Use |
| APScheduler 3.11 | taskiq 0.12.4 / dramatiq 2.2.0 | If/when work must run in separate worker processes (e.g., crawler pool). dramatiq tolerates redis 8 (`redis<9`); taskiq is async-native. Defer to the queue phase |
| Custom JWT (PyJWT+pwdlib) | Supabase Auth (email/OAuth + RLS) | If the platform becomes multi-tenant/client-facing auth. For the single-owner dashboard + approval gates, custom JWT is simpler and keeps one auth path for API + agents |
| SQLAlchemy async | Supabase REST-only data access | If every query stayed trivial CRUD. Lead scoring, finance rollups, and audit queries need real SQL — keep the ORM |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **langgraph 0.0.x pins** (`>=0.0.30`) | Pre-1.0 API is completely rewritten in 1.x (graph/state/interrupt/checkpoint all changed). Code written against 0.0.x won't port; docs/examples target 1.x | `langgraph>=1.2` + `langgraph-checkpoint-postgres>=3.1` |
| **langchain-core/langchain-openai explicit pins** (>=0.1.0/>=0.0.8) | Stale major-0 pins; langgraph 1.x pulls `langchain-core<2,>=1.4.7` transitively. Explicit ancient pins invite resolver conflicts and confusion | Remove the declarations; let langgraph manage langchain-core |
| **APScheduler 4.x** | Still alpha (4.0.0a6 as of 2026-08-04); API unstable | `apscheduler>=3.11,<4` |
| **arq (as queue)** | arq 0.28.0 hard-pins `redis[hiredis]<6` — conflicts with current redis-py 8.1 and forces the stack back 3 majors. The trap is silent: `uv add arq` downgrades redis | Redis Streams directly, or taskiq/dramatiq (redis 8 compatible) when a worker framework is needed |
| **Celery** | Sync-first worker model, awkward asyncio integration, heavyweight broker/admin surface — wrong shape for an async single-tenant stack | APScheduler (in-process) + Redis; taskiq/dramatiq if workers are needed |
| **RQ** | Sync workers only; no asyncio | See above |
| **Kafka** (SPEC-001 diagram lists it as bus alternative) | Massive operational overhead for a single-tenant daily-batch workload; Postgres (audit/state) + Redis (bus/queue) covers the MessageEnvelope pattern | Redis Streams/Postgres |
| **python-jose** | Ecosystem-deprecated; slow release cadence, historical CVEs. PyJWT is the maintained standard | `pyjwt>=2.13` |
| **passlib** | Unmaintained since 2020; breaks with bcrypt>=4.1 (`AttributeError: __about__`) | `pwdlib>=0.3` or direct `bcrypt>=5` |
| **python-dotenv** | Redundant — pydantic-settings already loads `.env` | Remove from pyproject |
| **stripe v7 / razorpay v1.4** | 8 majors / 1 major behind respectively; API surfaces changed (breaking) | Bump to stripe 15.x / razorpay 2.x *in the finance phase* — don't write new code against old majors |
| **pdfkit / wkhtmltopdf** | Dated, deprecated rendering path, extra binary dependency | WeasyPrint or Playwright `page.pdf()` |
| **Python `lighthouse` wrapper (1.0.0)** | Thin wrapper requiring Node + `lighthouse` CLI installed in the runtime — fragile on free tiers (Railway/VPS) | In-page metrics via Playwright (LCP/CLS/INP/TTFB through PerformanceObserver) + PageSpeed Insights API for official scores |
| **builtwith (tech detection)** | Paid API wrapper; recurring cost against the free-tier constraint | `wappalyzer>=2.0` (local patterns) + regex fallback |
| **Firecrawl (v1)** | Paid SaaS per-crawl pricing; violates "no paid API keys assumed" for the core crawling path | Playwright + own crawler; revisit if extraction quality becomes a bottleneck |
| **Next.js 14 / React 18 (declared)** | 2 majors / 1 major behind; Next 16 requires React 19 — build fresh on current majors | Next 16.3 + React 19.2 + Tailwind v4 |

## Stack Patterns by Variant

**If deploying as a single instance (v1 — recommended for the free-tier budget):**
- APScheduler 3.11 in-process cron + Redis (counters/cache) + LangGraph graphs run in-process with Postgres checkpointing. No worker fleet, no broker. Daily volumes (10–50 leads, 25 outreach) are trivially within one process.

**If crawling/audit volume grows (50+ audits/day):**
- Move Playwright work into separate worker processes (dramatiq 2.2 on redis 8, or taskiq) so browser launches never block the API event loop; keep the LangGraph state machine in-process.

**If the platform becomes multi-tenant / client-facing:**
- Adopt Supabase Auth (email/OAuth + RLS) for client portal; keep custom JWT for the owner; add per-tenant scoping to the repository layer.

**If real Lighthouse scores are required (not just field metrics):**
- Add PageSpeed Insights API v5 (free quota) as a sidecar scorer; keep Playwright metrics as the primary always-available signal.

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| langgraph 1.2.10 | langchain-core >=1.4.7,<2 (auto) | langgraph requires langgraph-checkpoint >=4.1,<5; langgraph-checkpoint-postgres 3.1.1 requires langgraph-checkpoint >=4.1 — all resolve together at 1.x |
| fastapi 0.141.1 | pydantic 2.13.4 | FastAPI supports pydantic v2 line; both current |
| sqlalchemy 2.0.51 | asyncpg 0.31.0, greenlet (via `[asyncio]` extra) | Pin `sqlalchemy[asyncio]>=2.0.51` so greenlet resolves; asyncpg 0.31 supports current CPython lines (verify 3.14 wheels at install — LOW confidence) |
| redis-py 8.1.0 | dramatiq (redis<9 ✓), rq (redis!=6 ✓) | **arq is incompatible** (requires redis<6) — the reason arq is excluded |
| next 16.3.0 | react 19.2.8 (required pairing) | Next 16 does not support React 18; the declared React 18 plan must move to 19 |
| tailwindcss 4.3.3 | @tailwindcss/postcss 4.3.3, Next 16 | v4 uses CSS-first config; no `tailwind.config.js`; shadcn/ui supports v4 |
| apscheduler 3.11.3 | — | Pin `<4`; 4.x alpha series (4.0.0a6) must not resolve |
| stripe 15.4.0 / razorpay 2.0.1 | — | Breaking migrations from declared v7 / v1.4 — schedule in finance phase with migration notes |
| weasyprint 69.0 | Python >=3.10, system libs (pango/cairo via Homebrew on macOS) | Needs `brew install pango libffi`-style system deps on macOS; document in setup |
| supabase 2.31.0 | SQLAlchemy path (asyncpg) independent of REST client | Keep both: ORM for queries, client for auth/storage/realtime |

## Gaps in pyproject.toml (explicit flags for the roadmap)

1. **`sqlalchemy` — CRITICAL.** Imported in `backend/database.py` today, undeclared. Any clean venv install fails at import. Add `sqlalchemy[asyncio]>=2.0.51`.
2. **`alembic` — CRITICAL.** No migration tooling; CONCERNS requires it; `create_all` in `init_db()` must be replaced.
3. **No lockfile — CRITICAL.** `>=`-only constraints + no lock = non-reproducible installs across dev/CI. Add uv + `uv.lock` in the foundation phase.
4. **`langgraph>=0.0.30` — CRITICAL.** Ancient pre-1.0 pin; replace with `>=1.2` at the orchestration phase (API-complete rewrite — plan the adoption as new work, not an upgrade).
5. **`stripe>=7.0.0` / `razorpay>=1.4.0`** — stale majors; bump at the finance phase.
6. **`redis>=5.0.0`** — bump to `>=8.1`.
7. **`python-jose` / `passlib`** — replace with PyJWT / pwdlib at the auth phase.
8. **Missing for planned features:** tenacity (retries), sentry-sdk (DSN already configured), email-validator, pgvector, langgraph-checkpoint-postgres, reppy, num2words, Babel, WeasyPrint (or use Playwright PDF), wappalyzer (MEDIUM confidence — verify maintenance), slowapi (or hand-rolled limiter).
9. **`python-dotenv`** — remove (redundant).
10. **Frontend** — nothing exists; scaffold with Next 16 + React 19 + Tailwind v4 (declared v4 correct; Next 14/React 18 outdated).

## Sources

- PyPI JSON API (`pypi.org/pypi/<pkg>/json`) — all Python versions verified 2026-08-04 — HIGH
- npm registry (`registry.npmjs.org/<pkg>/latest`) — next 16.3.0, react 19.2.8, tailwindcss 4.3.3, shadcn 4.16.1, recharts 3.10.1 — HIGH
- Context7 library `/websites/reference_langchain_python_langgraph` — `interrupt`/`Command` human-in-the-loop API verified — HIGH
- LangChain reference docs (reference.langchain.com/python/langgraph) — interrupt/checkpointer semantics — HIGH
- Dependency constraints inspected from PyPI metadata: langgraph (langchain-core<2,>=1.4.7), arq (redis<6 — incompatibility), langgraph-checkpoint-postgres (checkpoint>=4.1), crawlee/crawl4ai (playwright deps), dramatiq (redis<9), rq (redis!=6) — HIGH
- `.planning/codebase/STACK.md`, `INTEGRATIONS.md`, `CONCERNS.md` (2026-08-04) — as-built stack, integration status, dependency-at-risk analysis — HIGH (as-built ground truth)
- `pyproject.toml` (as-built) — declared pins audited — HIGH
- Qualitative ecosystem claims (pydantic-ai/CrewAI/OpenAI Agents SDK capabilities, wappalyzer maintenance, Lighthouse Python wrapper state) — **LOW/MEDIUM** — versions verified, behavioral claims from training data; re-verify in the relevant phase

---
*Stack research for: AI Agency OS — agent orchestration platform*
*Researched: 2026-08-04*
