<!-- GSD:project-start source:PROJECT.md -->

## Project

**AI Agency OS**

An autonomous AI-powered digital agency platform that finds leads, qualifies prospects, generates personalized outreach, negotiates within predefined limits, creates contracts, delivers projects, collects payments, and manages clients with minimal human intervention. The owner defines services, pricing rules, brand guidelines, legal templates, and approval limits; the AI operates the rest — an AI company with specialized departments (agents) instead of a single AI agent. Target market: businesses needing websites, automations, AI chatbots, and custom internal AI systems.

**Core Value:** A self-operating agency pipeline: continuously discover qualified opportunities → convert them through an autonomous sales/legal/finance loop → deliver projects and lock in recurring monthly revenue — all with human approval only at defined gates (contracts, payments, commitments outside pricing rules).

### Constraints

- **Tech stack (declared):** Python 3.11+ / FastAPI / SQLAlchemy async / Supabase (PostgreSQL + pgvector) / Redis / httpx; frontend planned Next.js 14 + React 18 + Tailwind v4; AI via OpenRouter (free), Google AI Studio (free), Groq (free), Ollama (local) — no paid API keys assumed
- **Budget:** free/low-cost tiers wherever possible (per PRD AI section); deployment to free tiers of Vercel/Cloudflare/Netlify where feasible
- **Compliance:** platform terms + robots.txt + anti-spam law must be respected — this constrains scraping/outreach designs
- **Approval gates:** contracts, payment collection, and commitments outside pricing rules require explicit human approval
- **Timeline (legacy):** original 10-week/8-milestone plan; will be re-derived by roadmap
- **Dependency integrity:** `pyproject.toml` missing `sqlalchemy`; `langgraph>=0.0.30` pin is ancient; no lockfile — must fix during foundation phase

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python >=3.11 (declared in `pyproject.toml` `requires-python`) — entire backend is Python. Dev machine runs Python 3.14.5. No runtime pin file (`.python-version`/`runtime.txt`) present.
- None in code. TypeScript/Next.js 14/React 18/Tailwind are specified in `.planning/legacy/PROJECT.md` and `.planning/specs/development/SPEC-004-development-pipeline.md` as the planned frontend stack for client deliverables, but `frontend/` is empty — no frontend code exists yet.

## Runtime

- Python 3.11+ (no version manager pinning, no Dockerfile, no container config)
- pip/setuptools via `pyproject.toml` (`[build-system]` requires setuptools>=68.0 + wheel)
- Lockfile: **missing** — no `requirements.txt`, `poetry.lock`, `uv.lock`, or `Pipfile` anywhere

## Frameworks

- FastAPI >=0.109.0 — declared in `pyproject.toml`, **not yet instantiated** (no app entry point, `backend/` has no `main.py`/`app.py`)
- Pydantic 2 >=2.5.0 + pydantic-settings >=2.1.0 — **actively used** in `backend/config.py` (Settings class)
- SQLAlchemy 2.0 async ORM (`sqlalchemy.ext.asyncio` + DeclarativeBase) — **actively used** in `backend/database.py`, but **NOT declared in `pyproject.toml`** (dependency gap — see CONCERNS)
- Uvicorn[standard] >=0.27.0 — declared, unused so far
- LangGraph >=0.0.30, langchain-core >=0.1.0, langchain-openai >=0.0.8 — declared; **agent code does NOT use them** — `backend/agents/base.py` calls LLM providers via raw `httpx.AsyncClient` instead
- Supabase >=2.3.0 (`supabase.create_client`) — actively used in `backend/database.py:290`
- pytest >=7.4.0, pytest-asyncio >=0.23.0, pytest-cov >=4.1.0 — declared in `[project.optional-dependencies] dev`; `tests/` directory exists but is **empty** — no tests written yet
- black (line-length 100, target py311), ruff (line-length 100, target py311), mypy (`disallow_untyped_defs = true`, `warn_return_any = true`) — all configured in `pyproject.toml` tool sections

## Key Dependencies

- `pydantic` / `pydantic-settings` — config system, `backend/config.py:8`
- `supabase` — REST client for Supabase, `backend/database.py:7`
- `sqlalchemy` — async ORM engine/session/models, `backend/database.py:8` (undeclared dep)
- `asyncpg` — Postgres async driver (dialect string rewrite `postgresql://` → `postgresql+asyncpg://`, `backend/database.py:277`)
- `httpx` — all LLM provider calls (OpenRouter/Groq/Gemini), `backend/agents/base.py:54-125`
- `loguru` — logging, `backend/agents/base.py:9`
- `fastapi`, `uvicorn` — API layer planned, no routes exist
- `redis` — declared, `REDIS_URL` configured in `backend/config.py:89`, no usage in code
- `playwright` — declared, `PLAYWRIGHT_HEADLESS` flag in `backend/config.py:43`, no usage yet (planned for website auditing per `.planning/specs/discovery/SPEC-002-lead-discovery-engine.md`)
- `langgraph`, `langchain-core`, `langchain-openai`, `openai` — orchestration/SDKs declared, unused in code
- `jinja2` — templates declared; `backend/templates/{contracts,emails,proposals}/` exist but are empty
- `razorpay`, `stripe` — payment SDKs declared, configured in `backend/config.py:59-64`, no usage
- `sendgrid` — email SDK declared, configured in `backend/config.py:50-51`, no usage
- `apscheduler` — scheduler declared, scheduling settings in `backend/config.py:92-95`, no usage
- `python-multipart`, `python-jose[cryptography]`, `passlib[bcrypt]` — forms/JWT/hashing declared, no usage
- `python-dotenv` — declared (redundant; pydantic-settings loads `.env` itself via `Config.env_file`)
- `asyncpg` (DB driver), `supabase` (managed Postgres REST + auth client), `redis` (planned queue/cache — unused)

## Configuration

- pydantic-settings `BaseSettings` with `env_file = ".env"`, `extra = "ignore"`, case-insensitive aliases — `backend/config.py:169-173`
- `.env.example` present (111 lines) documenting ~50 variables across 12 groups: agency identity, database, AI providers, model assignments, search/scraping, email/communications, WhatsApp, payments, deployment targets, monitoring, guardrails, Redis, scheduler
- `.env` itself: **not present** (only `.env.example`)
- Settings instance exported as module singleton `settings = get_settings()` with `lru_cache` — `backend/config.py:176-183`
- Hardcoded business data in config: service catalog dict (4 service types, 15 packages), industry multipliers (15 industries), size multipliers (5), urgency multipliers (4), condition multipliers (5) — `backend/config.py:98-167`
- `pyproject.toml` — single source of truth; `[tool.black]`, `[tool.ruff]`, `[tool.mypy]` sections
- No `setup.cfg`, `tox.ini`, `Makefile`, or CI config files

## Platform Requirements

- Python 3.11+ (dev machine: 3.14.5)
- Local Redis expected at `redis://localhost:6379/0` (default `REDIS_URL`)
- Local Ollama expected at `http://localhost:11434` (default `OLLAMA_BASE_URL`)
- Playwright browsers (once crawling is implemented)
- Nothing deployed; no Dockerfile, no docker-compose, no CI/CD config
- Planned targets (tokens configured in `backend/config.py:67-71`): Vercel, Cloudflare, Netlify; PROJECT.md also lists Railway/VPS
- Specs assume PostgreSQL + pgvector (`.planning/specs/core/SPEC-001-core-system-architecture.md`), Redis (Kafka mentioned as alternative in spec architecture diagram)

## Notes

- Git repo initialized on `main` with **zero commits** — entire codebase is untracked
- `README.md` referenced by `pyproject.toml` (`readme = "README.md"`) does not exist; no `.gitignore` present
- No `__init__.py` files exist anywhere — `backend.*` imports (`backend/config`, `backend/database`, `backend.agents.*`) resolve via implicit namespace packages only when running from repo root
- Backend structure is a skeleton: implemented files are `backend/config.py`, `backend/database.py`, `backend/agents/{base,ceo,lead_hunter}.py`; everything else (`backend/tools/`, `backend/workflows/`, `backend/templates/*/`, `src/*`, `automations/`, `config/`, `deploy/`, `scripts/`, `frontend/`, `tests/`, `docs/`) is empty scaffolding

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- All Python files are lowercase `snake_case.py`: `backend/config.py`, `backend/database.py`, `backend/agents/base.py`, `backend/agents/ceo.py`, `backend/agents/lead_hunter.py`
- Files containing a primary class use the class's role, not the class name: `ceo.py` contains `CEOAgent`, `lead_hunter.py` contains `LeadHunterAgent`
- PascalCase: `Settings` (`backend/config.py:8`), `BaseAgent` (`backend/agents/base.py:25`), `CEOAgent` (`backend/agents/ceo.py:7`), `LeadHunterAgent` (`backend/agents/lead_hunter.py:10`), `AgentContext` (`backend/agents/base.py:15`), `Business`, `Audit`, `Proposal` (`backend/database.py:89,121,144`)
- Enums are PascalCase with UPPER_SNAKE members: `class BusinessStatus(str, enum.Enum)` with `DISCOVERED`, `CLOSED_WON` (`backend/database.py:24-31`)
- Abstract role bases use role noun + `Agent`: `DiscoveryAgent`, `AuditAgent`, `SalesAgent`, `NegotiationAgent`, `DeliveryAgent`, `OpsAgent` (`backend/agents/base.py:176-250`)
- snake_case: `get_settings`, `init_db`, `get_db`, `close_db` (`backend/config.py:177`, `backend/database.py:270-303`)
- Private/internal methods prefixed with single underscore: `_call_openrouter`, `_call_groq`, `_call_gemini` (`backend/agents/base.py:68-108`), `_review_proposal`, `_handle_escalation`, `_set_strategy`, `_review_kpis` (`backend/agents/ceo.py:56-102`), `_discover_leads`, `_enrich_lead` (`backend/agents/lead_hunter.py:61,73`)
- Abstract methods declared with `@abstractmethod` and `pass` body: `get_default_system_prompt`, `execute` (`backend/agents/base.py:35-43`)
- snake_case: `business_id`, `proposal_id`, `mock_leads`, `supabase_client` (`backend/agents/base.py:17-22`, `backend/agents/lead_hunter.py:70`, `backend/database.py:267`)
- Module-level mutable globals are lowercase: `engine`, `async_session_maker`, `supabase_client` (`backend/database.py:265-267`)
- Config field names are snake_case with UPPER_SNAKE env-var aliases: `agency_name: str = Field(default="Nexus AI Agency", alias="AGENCY_NAME")` (`backend/config.py:12`)
- Type hints are built from `typing` generics: `Dict[str, Any]`, `List[Dict]`, `Optional[str]`, `AsyncGenerator`
- Imports use direct member imports: `from typing import Dict, List, Optional, Any, AsyncGenerator` (`backend/agents/base.py:6`)
- `Optional[X]` used for nullable fields and optional parameters; never bare `X = None` without annotation

## Code Style

- Tool: black, configured in `[tool.black]` (`pyproject.toml:47-49`)
- Line length: 100 (`line-length = 100`)
- Target: Python 3.11 (`target-version = ['py311']`)
- 4-space indentation; 2 blank lines between top-level classes/functions; 1 blank line between methods
- **Status note:** the codebase is NOT currently black-formatted — 49 lines across the 5 Python files exceed 100 characters (17 in `backend/config.py`, 24 in `backend/database.py`, 4 in `backend/agents/base.py`, 2 in `backend/agents/ceo.py`, 2 in `backend/agents/lead_hunter.py`). Run `black backend/` before adding new code.
- Trailing whitespace exists on blank lines inside class bodies (e.g. `backend/config.py:9-10`); `black`/`ruff` would clean this
- Tool: ruff, configured in `[tool.ruff]` (`pyproject.toml:51-53`)
- Line length: 100; target: py311
- No explicit rule selection — defaults apply
- Ruff would flag existing issues: unused imports (`os`, `asyncio`, `AsyncGenerator` in `backend/agents/base.py:2-6`; `json`, `asyncio` in `backend/agents/lead_hunter.py:2-3`; `List`, `Optional` in `backend/config.py:3`), bare `except:` at `backend/agents/base.py:169` (E722), out-of-order import `import enum` at `backend/database.py:14` (E402/I001)

## Import Organization

- No `src`-layout or path aliases configured; imports are absolute from repo root using `backend.` prefix (`from backend.config import settings`, `from backend.agents.base import DiscoveryAgent, AgentContext`)
- Exception to stdlib-first order: `import enum` appears after the `backend.config` import at `backend/database.py:14` — do not replicate; keep stdlib together at the top

## Error Handling

- Broad `try/except Exception` around LLM calls; log via `logger.error` and return an error-string rather than raising: `logger.error(f"LLM call failed for {self.name}: {e}")` then `return f"ERROR: {str(e)}"` (`backend/agents/base.py:64-66`)
- Result-envelope dicts for agent operations: `{"success": True, "data": ..., "raw": ...}` on success (`backend/agents/base.py:168-172`) and `{"success": False, "error": "No proposal ID in context"}` on failure (`backend/agents/ceo.py:59`)
- `raise NotImplementedError` marks unimplemented interface methods on specialized base agents (`backend/agents/base.py:181,185,193,197,205,209,217,231,235,239,247,251`)
- HTTP status handling via `response.raise_for_status()` on httpx responses (`backend/agents/base.py:86,105,124`); exceptions propagate to the caller's `except Exception`
- Bare `except: pass` around JSON parsing of LLM output (`backend/agents/base.py:169`) — prefer `except (ValueError, TypeError)` or log the failure instead
- Guard clauses return early with an error envelope before doing work (`backend/agents/ceo.py:58-59`)

## Logging

- Logging is used only in `backend/agents/base.py` — the three existing call sites are the convention:
- Log messages use f-strings with `[AgentName]` prefixes and truncate long inputs (`task[:100]`)
- `backend/config.py`, `backend/database.py`, `backend/agents/ceo.py`, `backend/agents/lead_hunter.py` contain no logging
- No `logger.add(...)` sink configuration anywhere; loguru defaults apply
- `print()` is not used anywhere in the codebase

## Comments

- Section banners with `# ====` separators group related declarations in `backend/database.py:21-23, 86-88, 262-264`
- Inline trailing comments document column semantics on SQLAlchemy models: `# DESIGN, FRONTEND, BACKEND, TESTING, DEVOPS` (`backend/database.py:214`), `# Agent name` (`backend/database.py:216`), `# SENT, DELIVERED, OPENED, REPLIED, BOUNCED` (`backend/database.py:257`)
- Placeholder comments mark known-skeleton code: `# In production, this would call actual APIs` (`backend/agents/ceo.py:61`, `backend/agents/lead_hunter.py:68`), `# Implementation would use actual APIs` (`backend/agents/lead_hunter.py:116`), `# Last 10 exchanges` (`backend/agents/base.py:132`)
- Config section comments group settings: `# Agency Identity`, `# Database`, `# AI Providers` (`backend/config.py:11-30`)
- No TODO/FIXME/HACK comments exist in the codebase (the only `TODO` matches are the `TaskStatus.TODO` enum member, `backend/database.py:79`)
- Every module has a one-line module docstring: `"""Core configuration module for AI Agency OS."""` (`backend/config.py:1`), `"""Database connection and models for AI Agency OS."""` (`backend/database.py:1`)
- Every class has a one-line class docstring: `"""Application settings loaded from environment variables."""` (`backend/config.py:9`), `"""Abstract base class for all agency agents."""` (`backend/agents/base.py:26`)
- Public methods have one-line docstrings: `"""Get cached settings instance."""` (`backend/config.py:178`), `"""Execute a task with the given context."""` (`backend/agents/base.py:42`)
- Abstract method bodies are a docstring followed by `pass` (`backend/agents/base.py:35-38`)
- Docstring style is plain triple-quoted one-liners — no Google/NumPy/Sphinx sections, no parameter/return annotations in docstrings (signatures carry that via type hints)
- Gaps: `set_context` and `register_tool` lack docstrings (`backend/agents/base.py:45-49`), as do all `__init__` methods — give new public methods a one-line docstring

## Function Design

- Every parameter is type-annotated — required by mypy `disallow_untyped_defs` (`pyproject.toml:58`)
- Optional parameters use `Optional[X] = None` defaults: `def __init__(self, name: str, model: Optional[str] = None, system_prompt: Optional[str] = None)` (`backend/agents/base.py:28`)
- Numeric defaults inline: `temperature: float = 0.7`, `max_tokens: int = 4000` (`backend/agents/base.py:51`), `limit: int = 10` (`backend/agents/base.py:179`)
- Every function declares a return type — required by mypy `warn_return_any` (`pyproject.toml:57`)
- Agent execution returns the `Dict[str, Any]` envelope `{"success": bool, "data": ..., "raw": ...}` (`backend/agents/base.py:168-172`)
- LLM calls return `str`; DB session getters return `AsyncSession` (`backend/database.py:293`); possibly-missing singletons return `Optional[Client]` (`backend/database.py:306`)
- Module lifecycle functions are `async def` and return `None`: `init_db`, `close_db` (`backend/database.py:270,299`)

## Module Design

- `backend/config.py` exports class `Settings` plus an instantiated module-level singleton: `settings = get_settings()` (`backend/config.py:183`); `get_settings` is memoized with `@lru_cache()` (`backend/config.py:176-179`)
- `backend/database.py` exports SQLAlchemy `Base`, status enums, models, lifecycle functions (`init_db`, `get_db`, `close_db`, `get_supabase`), and module-level globals `engine`/`async_session_maker`/`supabase_client` (`backend/database.py:265-267`)
- `backend/agents/base.py` exports `AgentContext` dataclass and agent base classes; `ceo.py`/`lead_hunter.py` export concrete agents
- No `__init__.py` exists in `backend/` or `backend/agents/` — there are no barrel files; imports reference modules directly (`from backend.agents.base import ...`)
- Empty placeholder directories with no code: `backend/tools/`, `backend/workflows/`, `src/` (with `agents/`, `api/`, `core/`, `services/`, `workflows/` subdirs), `automations/`, `config/`, `deploy/`, `docs/`, `frontend/`, `scripts/`, `tests/`

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `Settings` | All env-var configuration: agency identity, DB, AI providers, model assignments, pricing guardrails, service catalog, pricing multipliers | `backend/config.py` |
| `get_settings()` | Cached settings singleton (lru_cache) | `backend/config.py:176` |
| `Base` + ORM models | SQLAlchemy declarative base and 9 models: Business, Audit, Proposal, Contract, Project, Task, MaintenanceCheck, OutreachLog + 7 status enums | `backend/database.py` |
| `init_db()` | Creates async engine, session maker, and Supabase client; creates tables via `Base.metadata.create_all` | `backend/database.py:270` |
| `BaseAgent` | Abstract base: name/model/system_prompt, context, tool registry, multi-provider LLM dispatch (`call_llm`), message building, `run()` entry | `backend/agents/base.py:25` |
| `AgentContext` | Dataclass carrying business/proposal/contract/project IDs + metadata + conversation history between agents | `backend/agents/base.py:14` |
| `LLMAgent` | Concrete LLM agent with optional structured-output (JSON) parsing | `backend/agents/base.py:145` |
| Role bases (`DiscoveryAgent`, `AuditAgent`, `SalesAgent`, `NegotiationAgent`, `DeliveryAgent`, `OpsAgent`) | Typed method contracts per department; most raise `NotImplementedError`; `NegotiationAgent.check_guardrails` implemented | `backend/agents/base.py:176-251` |
| `CEOAgent` | Strategy, proposal approval (`_review_proposal`), escalation (`_handle_escalation`), strategy (`_set_strategy`), KPI review (`_review_kpis`) — keyword-dispatched in `execute` | `backend/agents/ceo.py` |
| `LeadHunterAgent` | Lead discovery (`_discover_leads` — currently returns mock data), enrichment (`enrich_business`), search (`search_businesses` — placeholder) | `backend/agents/lead_hunter.py:10` |
| `MarketScannerAgent` | Market intelligence briefs; generic LLM passthrough | `backend/agents/lead_hunter.py:147` |
| Templates / Tools / Workflows dirs | Empty scaffolds for Jinja2 templates (contracts/emails/proposals), reusable tools, and LangGraph workflows | `backend/templates/`, `backend/tools/`, `backend/workflows/` |

## Pattern Overview

- Abstract base class (`BaseAgent`) defines the contract; department-specific role bases (`DiscoveryAgent`, `SalesAgent`, …) add typed method stubs; concrete agents (`CEOAgent`, `LeadHunterAgent`) subclass role bases
- All agent outputs use a uniform `{"success": bool, "data": ..., "raw": ...}` dict shape
- Configuration is centralized in one `Settings` class read from env vars with UPPER_SNAKE aliases
- LLM provider selection is automatic by which API key is configured (OpenRouter → Groq → Gemini), per `backend/agents/base.py:56-63`
- Agents are keyword-dispatched: `execute()` inspects the task string (`"discover"`, `"enrich"`, `"approve_proposal"`, `"escalation"`) to route to typed handlers
- Persistence is async SQLAlchemy with JSON columns for nested data; statuses are string-valued Python enums
- No web framework wiring yet — FastAPI is a declared dependency (`pyproject.toml`) but no app, routes, or entry point exist

## Layers

- Purpose: Single source of truth for all environment configuration and business guardrails
- Location: `backend/config.py`
- Contains: `Settings` (pydantic-settings), `get_settings()` cached singleton, module-level `settings` instance
- Depends on: `pydantic`, `pydantic-settings`, `.env` file (`Config.env_file = ".env"` at `backend/config.py:170`)
- Used by: `backend/database.py`, `backend/agents/base.py`, `backend/agents/ceo.py`, `backend/agents/lead_hunter.py`
- Purpose: ORM models, async engine, session management, Supabase client
- Location: `backend/database.py`
- Contains: `Base`, 9 models, 7 enums, `init_db()`, `get_db()`, `close_db()`, `get_supabase()`
- Depends on: `backend/config.py` (`settings`), SQLAlchemy async, supabase-py
- Used by: Not yet imported by any agent — models are defined but unused at runtime
- Purpose: Departmental AI agents that execute tasks via LLM calls
- Location: `backend/agents/`
- Contains: `base.py` (abstractions), `ceo.py`, `lead_hunter.py`
- Depends on: `backend/config.py`, `httpx`, `loguru`
- Used by: Nothing yet — no orchestrator, scheduler, or API invokes agents

## Data Flow

### Primary Request Path (as-built, agent-internal)

### Planned End-to-End Pipeline (per specs, not implemented)

- At runtime: mutable `self.context: AgentContext` on each agent instance (`backend/agents/base.py:32`); context is passed by object reference, not copied
- At rest: planned SQLAlchemy models (`backend/database.py`) cover businesses, audits, proposals, contracts, projects, tasks, maintenance checks, outreach logs
- Module-level globals: `engine`, `async_session_maker`, `supabase_client` in `backend/database.py:265-267`

## Key Abstractions

- Purpose: Contract for all agency agents — name, model, system prompt, context, tools, LLM dispatch, run entry
- Examples: `backend/agents/base.py:25`
- Pattern: Abstract base with `@abstractmethod get_default_system_prompt()` and `execute()`; template-method `run()` wraps execute with logging
- Purpose: Shared, mutable context envelope passed between agents in a workflow
- Examples: `backend/agents/base.py:14`
- Pattern: Dataclass with optional business/proposal/contract/project IDs, `metadata: Dict`, and `conversation_history: List[Dict]`
- Purpose: Typed department contracts — `DiscoveryAgent` (search/enrich businesses), `AuditAgent` (website audit), `SalesAgent` (outreach/objections), `NegotiationAgent` (guardrail-checked negotiation), `DeliveryAgent` (plan/build/deploy), `OpsAgent` (maintenance/reports)
- Examples: `backend/agents/base.py:176-251`
- Pattern: All methods raise `NotImplementedError` except `NegotiationAgent.check_guardrails()` (`backend/agents/base.py:219`), which enforces minimum price
- Purpose: Environment-driven configuration with defaults; fields map to UPPER_SNAKE env vars via aliases
- Examples: `backend/config.py:8`
- Pattern: `@lru_cache get_settings()` singleton (`backend/config.py:176`); module-level `settings = get_settings()` instance (`backend/config.py:183`); pricing guardrails and service catalog live here
- Purpose: Persistence schema for the full agency lifecycle (lead → audit → proposal → contract → project → maintenance)
- Examples: `backend/database.py:24-260`
- Pattern: SQLAlchemy 2.0 `Mapped`/`mapped_column` typing; UUID primary keys (`uuid4` default); string-based `enum.Enum` subclasses for statuses; JSON columns for lists/dicts

## Entry Points

## Architectural Constraints

- **Async-only runtime:** All agent execution and DB access is `async` (`backend/agents/base.py:41`, `backend/database.py:270`); LLM calls block via `httpx.AsyncClient` await
- **Global state:** Module-level mutable singletons — `settings` (`backend/config.py:183`) and `engine`/`async_session_maker`/`supabase_client` (`backend/database.py:265-267`) — initialized lazily by `init_db()`; multiple `init_db()` calls would recreate globals
- **No `__init__.py` files:** The repo has zero `__init__.py` files, so `backend`, `backend.agents`, `backend.tools`, `backend.workflows`, `src.*` resolve as implicit namespace packages; packages will be created once files are added
- **Package imports assume `backend` on path:** `from backend.config import settings` (`backend/database.py:13`) requires running from the repo root or installing the project
- **Single-file layering:** `backend/database.py` holds ALL models and enums (308 lines); `backend/agents/base.py` holds the entire agent abstraction hierarchy (251 lines)
- **Mock data in place of integrations:** `LeadHunterAgent._discover_leads` returns hardcoded mock leads (`backend/agents/lead_hunter.py:70-103`); `search_businesses` returns a placeholder (`backend/agents/lead_hunter.py:114`); `CEOAgent._review_proposal` does not read the DB (`backend/agents/ceo.py:61`)
- **String-keyword dispatch:** Agent behavior routes on substring matching of the task text (`"discover" in task.lower()` at `backend/agents/lead_hunter.py:50`; `"approve_proposal" in task.lower()` at `backend/agents/ceo.py:41`) — fragile to ambiguous task wording
- **Money as `float`:** Prices are Python `float` (`backend/config.py:78-86`, `backend/database.py`), not `Decimal` — a risk for financial precision

## Anti-Patterns

### Error strings as control flow

### Keyword-matching dispatch

### Bare `except: pass` in JSON parsing

### Unwired persistence

## Error Handling

- `call_llm` wraps the entire provider dispatch in `try/except` and logs via `logger.error(f"LLM call failed for {self.name}: {e}")` (`backend/agents/base.py:64-66`)
- `LLMAgent.execute` returns `{"success": True, ...}` with whatever it got — including error strings
- Role-base methods raise `NotImplementedError` to signal unimplemented contracts (`backend/agents/base.py:181-249`)
- `CEOAgent._review_proposal` returns `{"success": False, "error": "No proposal ID in context"}` for missing context (`backend/agents/ceo.py:58-59`)
- `NegotiationAgent.check_guardrails` returns `{"allowed": False, "min_price": ..., "reason": "..."}` for guardrail violations (`backend/agents/base.py:219-223`)

## Cross-Cutting Concerns

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
