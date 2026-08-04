# Codebase Concerns

**Analysis Date:** 2026-08-04

## Tech Debt

**Agent layer is ~90% stubs:**
- Issue: Every specialized agent base class in `backend/agents/base.py` defines its methods as `raise NotImplementedError` — `DiscoveryAgent.search_businesses`/`enrich_business` (lines 179-185), `AuditAgent.audit_website`/`analyze_technologies` (191-197), `SalesAgent.generate_outreach`/`handle_objection` (203-209), `NegotiationAgent.negotiate` (215-217), `DeliveryAgent.create_project_plan`/`build_deliverable`/`deploy` (229-239), `OpsAgent.run_maintenance_check`/`generate_report` (245-251). Only `CEOAgent` (`backend/agents/ceo.py`) and `LeadHunterAgent` (`backend/agents/lead_hunter.py`) have partial implementations. The ROADMAP (`/Users/hridey/ai-agency-os/.planning/legacy/ROADMAP.md`) promises 15+ specialized agents across 8 milestones; the Sales, Legal, Finance, QA, and Maintenance departments do not exist at all.
- Files: `backend/agents/base.py`, `backend/agents/ceo.py`, `backend/agents/lead_hunter.py`
- Impact: No agent outside discovery/CEO can run; the system cannot perform audit, outreach, negotiation, delivery, or maintenance — the core value proposition is unimplemented.
- Fix approach: Implement agents department-by-department in milestone order (M1 framework first, then M2 discovery), replacing stubs with real implementations backed by the spec docs in `.planning/specs/`.

**Hardcoded mock data in lead discovery:**
- Issue: `LeadHunterAgent._discover_leads` (`backend/agents/lead_hunter.py:61-112`) returns two hardcoded mock businesses ("Apex Dental Clinic", "Spice Route Restaurant") with fake phones (`+91-98765-43210`), and `search_businesses` (lines 114-127) returns a canned "Sample Business" record. Comment admits: "In production, this would call actual APIs. For now, return structured mock data showing the schema." `enrich_business` (lines 129-144) is a pass-through that just re-copies existing fields.
- Files: `backend/agents/lead_hunter.py`
- Impact: If this code is wired to the scheduler/API before real sources (Google Places/SerpAPI, per SPEC-002), fabricated leads flow into the pipeline and get audited/contacted.
- Fix approach: Implement real source integrations behind the `DiscoveryAgent` interface; gate mock mode behind an explicit `MOCK_MODE=true` env flag so it can never ship by default.

**CEO agent auto-approves without data:**
- Issue: `CEOAgent._review_proposal` (`backend/agents/ceo.py:56-71`) returns `"decision": "APPROVED"` unconditionally unless a `requires_human` metadata flag is set, with comment "In production, fetch proposal from DB. For now, return approval framework." The actual proposal, price, and guardrail math are never read. `_review_kpis` (lines 102-118) returns hardcoded zero KPIs.
- Files: `backend/agents/ceo.py`
- Impact: This is the human approval gate (a compliance-critical feature per `.planning/legacy/PROJECT.md` "Explicit approval required for contracts, payments, commitments outside pricing rules"). As written, the AI rubber-stamps financial decisions with no evidence.
- Fix approach: Require a proposal record (or DB fetch) before `_review_proposal` can return APPROVED; only auto-approve when price is below `settings.auto_approve_threshold` and discount below `settings.max_discount_percentage`; otherwise return `REQUIRES_HUMAN` with the guardrail breakdown.

**Errors become LLM output:**
- Issue: `BaseAgent.call_llm` (`backend/agents/base.py:51-66`) wraps every failure in `try/except` and returns the string `"ERROR: {str(e)}"` or `"ERROR: No LLM API key configured"`. `LLMAgent.execute` (lines 152-172) then wraps this in `{"success": True, "data": {"response": "ERROR: ..."}}` — a failed LLM call looks like a successful run. The bare `except: pass` at line 169-170 silently swallows JSON parse failures too.
- Files: `backend/agents/base.py`
- Impact: Downstream code cannot distinguish real output from failure; error strings could be sent to clients as content, and structured parsing failures silently return raw text.
- Fix approach: Let transport/HTTP errors propagate (or return `success: False` with a structured error object); log with `logger.exception`; add a retry with exponential backoff for transient 429/5xx responses.

**Fragile import scheme:**
- Issue: Modules use absolute imports (`from backend.config import settings` in `backend/database.py:13`, `backend/agents/base.py:11`) but there is no `__init__.py` anywhere in the tree (verified: zero `__init__.py` files). Imports resolve only via implicit namespace packages when the repo root happens to be on `sys.path`.
- Files: `backend/config.py`, `backend/database.py`, `backend/agents/*.py`
- Impact: Any launch pattern other than "run from repo root with cwd on path" (e.g., `uvicorn backend.main:app` from a subdirectory, installed as a package, or Docker WORKDIR variations) breaks at import time.
- Fix approach: Add `__init__.py` to `backend/` and `backend/agents/` and make the package installable (the `[build-system]` block in `pyproject.toml` exists but `README.md`, referenced as `readme` at line 5, is missing — the build fails as-is).

**Empty aspirational directories:**
- Issue: 18 directories exist but are empty, implying structure that doesn't exist yet: `src/agents/`, `src/api/`, `src/core/`, `src/services/`, `src/workflows/`, `frontend/`, `automations/`, `config/`, `deploy/`, `docs/`, `scripts/`, `tests/`, `backend/templates/contracts/`, `backend/templates/emails/`, `backend/templates/proposals/`, `backend/tools/`, `backend/workflows/`, plus empty spec dirs `.planning/specs/{compliance,finance,growth,legal,maintenance,observability}/`.
- Impact: The repo looks larger than it is; new code could be placed in the wrong tree (there are two competing source roots: `backend/` and `src/`).
- Fix approach: Pick one source root (recommend `backend/` since all real code lives there), delete or repurpose `src/`, and document placement in STRUCTURE.md.

**Declared-but-unused dependencies:**
- Issue: `pyproject.toml` (lines 7-31) declares 24 runtime dependencies, but the five real source files only use `pydantic`, `pydantic-settings`, `supabase`, `sqlalchemy`, `asyncpg`, `loguru`, and `httpx`. Unused: `fastapi`, `uvicorn`, `redis`, `playwright`, `langgraph`, `langchain-core`, `langchain-openai`, `openai`, `razorpay`, `stripe`, `sendgrid`, `apscheduler`, `python-jose`, `passlib`, `jinja2`, `python-multipart`, `python-dotenv`.
- Files: `pyproject.toml`
- Impact: Install surface and supply-chain risk without benefit; signals that scaffolding was written ahead of implementation.
- Fix approach: Strip to what the current phase needs; re-add each dependency in the phase that actually uses it (per `.planning/specs/`).

**No DB migration tooling:**
- Issue: `init_db()` in `backend/database.py:270-290` creates tables via `Base.metadata.create_all`; there is no Alembic, no migration history, no `__init__.py`-guarded versioning. ROADMAP Phase 1.2 explicitly requires Alembic migrations.
- Files: `backend/database.py`
- Impact: Schema changes require manual `create_all` teardown/rebuild; deployed environments will drift from dev.
- Fix approach: Add Alembic (`alembic init`) with an initial autogenerated revision and CI check that migrations are up to date.

## Known Bugs

**Placeholder identity values shipped as defaults:**
- Symptoms: `backend/config.py` ships business-critical values as hardcoded defaults: `agency_owner_email="owner@example.com"` (line 13), `agency_phone="+91-9876543210"` (line 15), `sendgrid_from_email="outreach@yourdomain.com"` (line 51), `agency_address="Mumbai, India"` (line 16). Financial guardrails also default: `min_website_starter=10000.0`, `auto_approve_threshold=50000.0`, `max_discount_percentage=15.0` (lines 78-86). Because `Config.env_file = ".env"` (`backend/config.py:170`) resolves relative to the process CWD, running from any directory other than the repo root silently skips `.env` and every default applies.
- Files: `backend/config.py`
- Trigger: Launch without a `.env` in the CWD, or with an incomplete `.env`.
- Workaround: None — values are silently accepted; there is no validation that identity fields are set or that emails/phones look real.
- Fix approach: Make identity fields required (no defaults) so startup fails loudly when unset; add a `validate()` method that rejects example.com/yourdomain placeholders; anchor `env_file` to the project root.

**`get_db()` crashes when `init_db()` was never called:**
- Symptoms: `get_db` (`backend/database.py:293-296`) does `async with async_session_maker() as session` — `async_session_maker` is initialized to `None` (line 266) and only set inside `init_db()` (line 282). Calling `get_db` before `init_db` (or with no `DATABASE_URL` set) raises `TypeError: 'NoneType' object is not callable`.
- Files: `backend/database.py`
- Trigger: Any first-use of the dependency before explicit initialization; also any environment without `DATABASE_URL` where the app is expected to run on Supabase only.
- Fix approach: Raise a descriptive `RuntimeError("Database not initialized — call init_db() first")`; also fail fast in `init_db()` when neither `database_url` nor Supabase credentials are set.

**Naive URL scheme rewrite:**
- Symptoms: `settings.database_url.replace("postgresql://", "postgresql+asyncpg://")` (`backend/database.py:277`) corrupts URLs that already carry a driver (`postgresql+asyncpg://...` becomes `postgresql+asyncpg+asyncpg://...`) and silently skips non-postgres URLs.
- Files: `backend/database.py`
- Fix approach: Use `sqlalchemy.engine.URL.create` / `URL.make_dsn` or `urlparse`-based scheme rewrite.

**Deprecated `datetime.utcnow`:**
- Symptoms: `datetime.utcnow` used for every timestamp default (`backend/database.py:111-112, 141, 162-163, 181-182, 203-204, 222-224, 242, 258-259`; also `lead_hunter.py:141`). Deprecated since Python 3.12 and returns naive UTC — timezone-aware callers comparing with `datetime.now(timezone.utc)` will error.
- Files: `backend/database.py`, `backend/agents/lead_hunter.py`
- Fix approach: Replace with `datetime.now(timezone.utc)` and store tz-aware values.

## Security Considerations

**No `.gitignore` and zero git history:**
- Risk: The repo (`/Users/hridey/ai-agency-os/.git`) has **no commits** and there is **no `.gitignore`** (verified at repo root). `.env.example` exists untracked (mode 0600). The first `git add . && commit` will stage everything — any `.env` file created next to it will be committed with live API keys. pyproject.toml references 20+ secret-bearing config fields (`SUPABASE_SERVICE_KEY`, `OPENROUTER_API_KEY`, `RAZORPAY_KEY_SECRET`, `STRIPE_SECRET_KEY`, etc. in `backend/config.py:20-71`).
- Files: repo root (missing `.gitignore`), `backend/config.py`
- Current mitigation: None.
- Recommendations: Add `.gitignore` immediately (`.env`, `.env.*`, `!/.env.example`, `__pycache__/`, `.venv/`, etc.); make the first commit deliberate; consider `git-crypt` or SOPS for any secrets that must be versioned.

**No authentication or authorization anywhere:**
- Risk: `python-jose[cryptography]` and `passlib[bcrypt]` are declared in `pyproject.toml:29-30` but no code uses them — no user model (not in `backend/database.py`), no login, no JWT, no API to protect yet. Any owner dashboard or admin endpoint added without auth would expose: client PII (Business, Audit, Contract tables), payment intents (`payment_intent_id` in `backend/database.py:180`), and full negotiation history.
- Files: `backend/database.py`, `pyproject.toml`
- Recommendations: Ship auth (JWT + bcrypt hashing via the declared libs) in the same phase as the first HTTP endpoint; enforce per-role access (owner vs client per SPEC-001 personas).

**API key in URL query string (Gemini):**
- Risk: `_call_gemini` (`backend/agents/base.py:118`) appends `?key={settings.gemini_api_key}` to the request URL — API keys in URLs leak into access logs, proxy logs, and error traces. No retry or rate limiting on any provider call.
- Files: `backend/agents/base.py`
- Recommendations: Move the Gemini key to the `X-Goog-Api-Key` header; add structured redaction in loguru sinks (e.g., filter for `api_key`, `token`, `secret` field names).

**Compliance features unimplemented:**
- Risk: The specs and legacy docs mandate compliance controls that do not exist in code: robots.txt respect and rate limiting for the crawler (SPEC-002: "Rate Limit Compliance 100%", "Robots.txt Compliance 100%"), anti-spam compliance — unsubscribe, opt-out, physical address in outreach (SPEC-003 FR-014), GDPR Art. 17 erasure / DPDP India handling (SPEC-002 §16), and "human approval gates for critical actions" (SPEC-001). ROADMAP Phase 7.1 itemizes all of it. Zero implementation exists; `daily_lead_discovery_count` / `daily_outreach_limit` (config.py:92-93) are configuration values with no enforcement code. `Proposal.human_approval_required` (`backend/database.py:158`) is a column with no logic reading it.
- Files: `backend/config.py`, `backend/database.py`, `.planning/specs/discovery/SPEC-002-lead-discovery-engine.md`, `.planning/specs/sales/SPEC-003-sales-proposal-system.md`, `.planning/specs/core/SPEC-001-core-system-architecture.md`
- Current mitigation: None.
- Recommendations: Implement compliance middleware as part of the M1 foundation (rate-limit + robots.txt guard on all fetch paths, approval workflow service checking `human_approval_required`, unsubscribe/erasure endpoints) before any live outreach or crawling runs. This is a release blocker for Milestone 7 criteria.

## Performance Bottlenecks

**No measurable load yet — but async hygiene is already correct:**
- All I/O is async (`httpx.AsyncClient` in `backend/agents/base.py:68-125`, `asyncpg` engine in `backend/database.py:276-281`); no blocking calls detected in the hot paths. Nothing to optimize yet because there is no running system.
- Forward-looking issues:
  - LLM calls have a single 60s timeout with no retry/backoff (`backend/agents/base.py:70, 91, 116`); a transient provider failure fails the whole agent run.
  - No LLM response caching and no request concurrency control — daily limits exist in config but nothing enforces budget.
  - Agent execution is strictly sequential (`run` → `execute` → one `call_llm`); no pipeline parallelism for the discovery → audit → outreach chain.
- Files: `backend/agents/base.py`, `backend/config.py`
- Improvement path: Add retry with exponential backoff (httpx `transport`/decorator), per-provider rate limiters, and response cache keyed on (model, messages hash).

## Fragile Areas

**`settings` import-time singleton:**
- Files: `backend/config.py:176-183`
- Why fragile: `settings = get_settings()` executes at module import; tests and scripts importing `backend.config` get a frozen instance — monkeypatching env vars after import has no effect without `get_settings.cache_clear()`.
- Safe modification: In tests, use `get_settings.cache_clear()` before/after patching `os.environ`; keep `lru_cache` (it exists to avoid re-reading `.env`).
- Test coverage: None.

**Mutable dict/list column defaults:**
- Files: `backend/database.py:100-101, 107-110, 130-132, 139-140, 156, 161, 175-178, 198, 220-221, 236-239, 257`
- Why fragile: `mapped_column(JSON, default={})` and `default=[]` use a **single shared dict/list instance** (non-callable defaults are reused by SQLAlchemy). Any in-place mutation (e.g., `row.pain_points.append(...)` before flush) leaks across rows/objects.
- Safe modification: Replace with `default=dict` / `default=list` (callables) so every row gets a fresh container.
- Test coverage: None.

**Error-string propagation through agents:**
- Files: `backend/agents/base.py:62-66, 152-172`
- Why fragile: Every failure mode funnels into a string that downstream code treats as content; a misconfigured environment produces "successful" runs with `ERROR:` payloads.
- Safe modification: Handle `success: False` branches in any orchestrator that consumes agent results.
- Test coverage: None.

**DB init ordering:**
- Files: `backend/database.py:265-296`
- Why fragile: Module-level `None` globals (`engine`, `async_session_maker`, `supabase_client`) plus required `init_db()` call before any session use; no FastAPI lifespan wiring exists to guarantee ordering.
- Safe modification: Convert to a single `Database` class with lazy init, or wire `init_db`/`close_db` into the app lifespan as soon as the app entry point exists.
- Test coverage: None.

## Scaling Limits

**Current capacity:** Trivially zero-load — the system is a skeleton; DB pool is configured `pool_size=10, max_overflow=20` (`backend/database.py:279-280`), which is adequate for the configured daily volume (`daily_lead_discovery_count=10`, `daily_outreach_limit=25` in `backend/config.py:92-93`).
**Limits to plan for:**
- No queue anywhere — all work is inline synchronous agent calls; ROADMAP M8's "24/7 autonomous operation" is impossible until `redis` (declared in `pyproject.toml:14`, unused) backs a task queue and `apscheduler` (line 26, unused) drives the daily cycle.
- No horizontal scaling story: `init_db()`'s `create_all` on every worker start is fine for a single process, but multiple workers racing `create_all` is not (migrations replace this).
- Lead discovery count (10/day) is 5× below the ROADMAP M2 success criterion (50+ qualified leads/day); the `daily_lead_discovery_count` knob exists but nothing reads it to schedule work.
- Scaling path: add task queue + scheduler in M1 (as specced in `.planning/specs/core/SPEC-001`), then raise volume via config only.

## Dependencies at Risk

**`langgraph>=0.0.30` (and friends) pinned to ancient pre-1.0 releases:**
- Risk: `pyproject.toml:17-19` pins `langgraph>=0.0.30`, `langchain-core>=0.1.0`, `langchain-openai>=0.0.8`. `0.0.30` is an early-2024 pre-release line; the current line is multiple majors ahead with a completely different graph/state API. Any code written against 0.0.x will need a rewrite to upgrade. None of these are imported yet, so the pin is dormant risk — but it sets a trap: new code written against whatever `pip` resolves today (likely far newer) will silently diverge from the declared constraint.
- Impact: Upgrade pain when LangGraph orchestration is implemented (ROADMAP M1 Phase 1.1 requires LangGraph); docs/examples online target current APIs.
- Migration plan: Remove the pins until the orchestration phase; then pin to the current stable major and write code against it.

**`stripe>=7.0.0`:**
- Risk: `pyproject.toml:24` — major version 7 is years old (current is 10+ majors ahead). When the finance phase (M4) starts, the package will need a major upgrade with breaking API changes.
- Impact: Integration code written now against v7 would be dead on arrival.
- Migration plan: Bump to current stable when `backend/workflows/` finance flows are implemented.

**Also at risk:**
- `playwright>=1.40.0` (`pyproject.toml:16`) — requires `playwright install` browser download step not documented anywhere; crawler per SPEC-002 Phase 2.2 depends on it.
- `supabase>=2.3.0` (`pyproject.toml:12`) — functional but old; client API changed across later majors.
- **No lockfile** — no `requirements*.txt`, `uv.lock`, or `poetry.lock`; pip resolves unpinned transitive versions at install time. Combined with `>=`-only constraints, two developers or a CI run can install different trees.
- `python-dotenv` (`pyproject.toml:21`) is redundant — `pydantic-settings` already handles `.env` loading (`backend/config.py:170`).

## Missing Critical Features

**No FastAPI app entry point:**
- Problem: `fastapi`/`uvicorn` are declared (`pyproject.toml:8-9`) but there is no `main.py`/`app.py` anywhere. Nothing in the repo is runnable; `backend/` has no web layer, no routers, no lifespan wiring (`init_db`/`close_db` in `backend/database.py` have no caller), and `src/api/` is empty.
- Blocks: Every downstream phase; there is no way to serve, test, or demo the system.
- Fix approach: Create `backend/main.py` with FastAPI app, lifespan calling `init_db()`/`close_db()`, and a `/health` endpoint — this is the ROADMAP Phase 1.1 deliverable.

**No tests:**
- Problem: `tests/` is empty; zero test files exist despite `pytest`, `pytest-asyncio`, `pytest-cov` in dev extras (`pyproject.toml:35-37`).
- Fix approach: See Test Coverage Gaps below.

**No CI:**
- Problem: No `.github/` or any CI config; nothing runs lint (`ruff`/`black` configured in `pyproject.toml:47-53` but never executed), type checks (`mypy` configured at lines 55-59), or tests.
- Fix approach: Add a minimal GitHub Actions workflow (lint → typecheck → test) as part of M1.

**No database repositories layer:**
- Problem: ROADMAP Phase 1.2 requires a repository layer; `backend/database.py` defines models and session machinery only — all DB access would currently be ad-hoc SQLAlchemy queries in agent code.
- Fix approach: Add `backend/repositories/` with per-entity repositories before agents start persisting.

**No scheduler or queue:**
- Problem: `apscheduler` and `redis` declared but unused; the daily discovery/outreach/maintenance cycle described throughout ROADMAP and SPEC-001 has no trigger mechanism.
- Blocks: M2 lead discovery automation, M6 maintenance, M8 autonomous operation.

**No auth, no observability, no logging config:**
- Problem: loguru is used in `backend/agents/base.py` with defaults (no structured format, no redaction, no sinks); `sentry_dsn` config field exists (`backend/config.py:74`) but nothing sends to Sentry; no health checks, metrics, or tracing.
- Fix approach: Wire loguru config + Sentry in the app entry phase.

**No robots.txt / rate-limit / approval-gate middleware:**
- Problem: All compliance machinery from SPEC-002 (rate limit + compliance box in the crawler flow, §16), SPEC-003 (anti-spam, unsubscribe), and SPEC-001 (approval workflows) is absent — see Security Considerations.
- Blocks: Legal launch (M7 "Zero compliance issues").

## Test Coverage Gaps

**Overall coverage: zero — no test files exist (`tests/` directory is empty).**

| Untested area | What's not tested | Files | Risk | Priority |
|---|---|---|---|---|
| Config resolution | Env override, alias mapping, missing `.env` behavior, placeholder defaults | `backend/config.py` | Misconfigured environments run with example.com identity / fake guardrail values | High |
| Guardrails & pricing | Min-price floor, discount cap, auto-approve threshold, industry/size/urgency multipliers | `backend/config.py`, `backend/agents/base.py:219-223`, `backend/agents/ceo.py` | Financial decisions made without verification | High |
| Agent dispatch | CEO task-type routing, lead hunter discover/enrich/search routing | `backend/agents/ceo.py:36-54`, `backend/agents/lead_hunter.py:46-59` | Wrong agent path runs for a task; unhandled tasks fall through to generic LLM call | High |
| LLM client | OpenRouter/Groq/Gemini request building, JSON extraction, error paths | `backend/agents/base.py:51-172` | Error strings shipped as content; broken structured output | High |
| DB models | Enum constraints, FK cascade behavior, JSON defaults, index creation | `backend/database.py` | Schema drift; shared mutable defaults leak across rows | Medium |
| DB lifecycle | `init_db`/`get_db`/`close_db` ordering, missing-URL behavior | `backend/database.py:270-303` | TypeError on uninitialized session maker | Medium |
| Compliance | Rate-limit enforcement, robots.txt handling, approval gates | (none — feature missing) | Legal exposure; fake approvals on real money | High (when implemented) |

- What's not tested, specific: zero unit, integration, or E2E tests for any module; no `pytest.ini`/`pyproject.toml [tool.pytest.ini_options]`; no asyncio test plugin configuration despite `pytest-asyncio` being declared.
- Files: `tests/` (empty), `pyproject.toml:33-41`
- Risk: Regressions invisible across all planned phases; the first commit ships with no safety net.
- Priority: High — add pytest config + baseline unit tests (config validation, guardrail math, agent dispatch) in M1; cover DB layer with a test Postgres/SQLite async fixture.

---

*Concerns audit: 2026-08-04*
