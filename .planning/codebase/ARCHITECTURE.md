<!-- refreshed: 2026-08-04 -->
# Architecture

**Analysis Date:** 2026-08-04

## System Overview

The codebase is an early-stage skeleton. Only the agent abstraction layer and persistence/config foundations exist; the FastAPI API layer, workflows, tools, templates, and frontend are empty scaffold directories. The diagram below shows the as-built architecture, with planned (empty) layers marked.

```text
┌────────────────────────────────────────────────────────────────────┐
│                        AGENT LAYER (as-built)                       │
│  `backend/agents/`                                                 │
│  ┌───────────────┐   ┌──────────────────┐   ┌──────────────────┐   │
│  │  CEOAgent     │   │  LeadHunterAgent │   │ MarketScannerAgent│   │
│  │ `ceo.py`      │   │  `lead_hunter.py`│   │  `lead_hunter.py`│   │
│  └───────┬───────┘   └────────┬─────────┘   └────────┬─────────┘   │
│          │    specializes     │   specializes        │             │
│          ▼                    ▼                      ▼             │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  BaseAgent (ABC) — `backend/agents/base.py`                 │    │
│  │  subclasses: LLMAgent, DiscoveryAgent, AuditAgent,          │    │
│  │  SalesAgent, NegotiationAgent, DeliveryAgent, OpsAgent      │    │
│  └───────┬────────────────────────────┬───────────────────────┘    │
│          │                            │                             │
│          ▼                            ▼                             │
│  ┌──────────────────┐        ┌─────────────────────┐                │
│  │  AgentContext    │        │  call_llm() →       │                │
│  │  (dataclass,     │        │  httpx → OpenRouter │                │
│  │  `base.py:14`)   │        │  / Groq / Gemini    │                │
│  └──────────────────┘        └─────────────────────┘                │
└──────────────┬──────────────────────────────────────────────────────┘
               │ imports
               ▼
┌────────────────────────────────────────────────────────────────────┐
│                    CONFIG & DATA LAYER (as-built)                  │
│  `backend/config.py`  Settings (pydantic-settings, env aliases)     │
│  `backend/database.py` Base + 9 ORM models + async engine +         │
│                        Supabase client (module-level globals)      │
└────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────────┐
│   OUTPUT / STORAGE (planned, not yet wired)                        │
│   PostgreSQL via SQLAlchemy async (`backend/database.py:276`)      │
│   Supabase client (`backend/database.py:289`)                      │
│   LLM provider APIs (OpenRouter/Groq/Gemini via httpx)             │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  EMPTY SCAFFOLD LAYERS (directories exist, no files)               │
│  `src/api/` `src/services/` `src/core/` `src/workflows/` `src/agents/`│
│  `backend/workflows/` `backend/tools/` `backend/templates/*/`      │
│  `frontend/` `tests/` `automations/` `config/` `deploy/`           │
└────────────────────────────────────────────────────────────────────┘
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

**Overall:** Specialized-agent inheritance hierarchy over a single abstract base, with env-driven configuration and dataclass-based context passing. Follows the "AI Departments" model from `.planning/legacy/PROJECT.md` (CEO, Market Intelligence, Lead Hunter, Sales, Negotiation, etc.).

**Key Characteristics:**
- Abstract base class (`BaseAgent`) defines the contract; department-specific role bases (`DiscoveryAgent`, `SalesAgent`, …) add typed method stubs; concrete agents (`CEOAgent`, `LeadHunterAgent`) subclass role bases
- All agent outputs use a uniform `{"success": bool, "data": ..., "raw": ...}` dict shape
- Configuration is centralized in one `Settings` class read from env vars with UPPER_SNAKE aliases
- LLM provider selection is automatic by which API key is configured (OpenRouter → Groq → Gemini), per `backend/agents/base.py:56-63`
- Agents are keyword-dispatched: `execute()` inspects the task string (`"discover"`, `"enrich"`, `"approve_proposal"`, `"escalation"`) to route to typed handlers
- Persistence is async SQLAlchemy with JSON columns for nested data; statuses are string-valued Python enums
- No web framework wiring yet — FastAPI is a declared dependency (`pyproject.toml`) but no app, routes, or entry point exist

## Layers

**Configuration Layer:**
- Purpose: Single source of truth for all environment configuration and business guardrails
- Location: `backend/config.py`
- Contains: `Settings` (pydantic-settings), `get_settings()` cached singleton, module-level `settings` instance
- Depends on: `pydantic`, `pydantic-settings`, `.env` file (`Config.env_file = ".env"` at `backend/config.py:170`)
- Used by: `backend/database.py`, `backend/agents/base.py`, `backend/agents/ceo.py`, `backend/agents/lead_hunter.py`

**Data Layer:**
- Purpose: ORM models, async engine, session management, Supabase client
- Location: `backend/database.py`
- Contains: `Base`, 9 models, 7 enums, `init_db()`, `get_db()`, `close_db()`, `get_supabase()`
- Depends on: `backend/config.py` (`settings`), SQLAlchemy async, supabase-py
- Used by: Not yet imported by any agent — models are defined but unused at runtime

**Agent Layer:**
- Purpose: Departmental AI agents that execute tasks via LLM calls
- Location: `backend/agents/`
- Contains: `base.py` (abstractions), `ceo.py`, `lead_hunter.py`
- Depends on: `backend/config.py`, `httpx`, `loguru`
- Used by: Nothing yet — no orchestrator, scheduler, or API invokes agents

**Planned layers (directories exist, no code):** API (`src/api/`), services (`src/services/`), workflows (`backend/workflows/`), tools (`backend/tools/`), templates (`backend/templates/{contracts,emails,proposals}/`), frontend (`frontend/`).

## Data Flow

### Primary Request Path (as-built, agent-internal)

1. Caller constructs an `AgentContext` and invokes `BaseAgent.run(task)` (`backend/agents/base.py:137`) or `execute(task, context)` directly
2. `execute()` calls `set_context(context)` (`backend/agents/base.py:45`), then dispatches on task keywords to a typed handler (e.g., `CEOAgent._review_proposal` at `backend/agents/ceo.py:56`)
3. Handler builds messages via `build_messages(task)` (`backend/agents/base.py:127`), which prepends `system_prompt` and appends the last 10 `conversation_history` exchanges
4. `call_llm(messages, temperature, max_tokens)` (`backend/agents/base.py:51`) dispatches to `_call_openrouter` / `_call_groq` / `_call_gemini` based on configured keys
5. Each provider method POSTs chat-completion JSON via `httpx.AsyncClient(timeout=60.0)` and extracts the first choice's content
6. `LLMAgent.execute` optionally extracts JSON between first `{` and last `}` when `output_schema` is set (`backend/agents/base.py:159-170`)
7. Result returned as `{"success": True, "data": ..., "raw": ...}`

### Planned End-to-End Pipeline (per specs, not implemented)

1. Daily Scheduler → Market Scanner → Lead Collector → Business Analyzer → Opportunity Ranking (`.planning/specs/discovery/SPEC-002-lead-discovery-engine.md:210`)
2. Personalized Audit → Proposal Generator → Negotiation Agent → Contract Generator → Payment Collection (`.planning/specs/sales/SPEC-003-sales-proposal-system.md:237`)
3. Project Creation → Development → Testing → Deployment → Maintenance → Upsell (`.planning/specs/development/SPEC-004-development-pipeline.md:254`)
4. Orchestration via LangGraph + message bus + approval engine (`.planning/specs/core/SPEC-001-core-system-architecture.md:93`)

**State Management:**
- At runtime: mutable `self.context: AgentContext` on each agent instance (`backend/agents/base.py:32`); context is passed by object reference, not copied
- At rest: planned SQLAlchemy models (`backend/database.py`) cover businesses, audits, proposals, contracts, projects, tasks, maintenance checks, outreach logs
- Module-level globals: `engine`, `async_session_maker`, `supabase_client` in `backend/database.py:265-267`

## Key Abstractions

**BaseAgent (ABC):**
- Purpose: Contract for all agency agents — name, model, system prompt, context, tools, LLM dispatch, run entry
- Examples: `backend/agents/base.py:25`
- Pattern: Abstract base with `@abstractmethod get_default_system_prompt()` and `execute()`; template-method `run()` wraps execute with logging

**AgentContext (dataclass):**
- Purpose: Shared, mutable context envelope passed between agents in a workflow
- Examples: `backend/agents/base.py:14`
- Pattern: Dataclass with optional business/proposal/contract/project IDs, `metadata: Dict`, and `conversation_history: List[Dict]`

**Specialized role bases:**
- Purpose: Typed department contracts — `DiscoveryAgent` (search/enrich businesses), `AuditAgent` (website audit), `SalesAgent` (outreach/objections), `NegotiationAgent` (guardrail-checked negotiation), `DeliveryAgent` (plan/build/deploy), `OpsAgent` (maintenance/reports)
- Examples: `backend/agents/base.py:176-251`
- Pattern: All methods raise `NotImplementedError` except `NegotiationAgent.check_guardrails()` (`backend/agents/base.py:219`), which enforces minimum price

**Settings (pydantic-settings BaseSettings):**
- Purpose: Environment-driven configuration with defaults; fields map to UPPER_SNAKE env vars via aliases
- Examples: `backend/config.py:8`
- Pattern: `@lru_cache get_settings()` singleton (`backend/config.py:176`); module-level `settings = get_settings()` instance (`backend/config.py:183`); pricing guardrails and service catalog live here

**ORM models + status enums:**
- Purpose: Persistence schema for the full agency lifecycle (lead → audit → proposal → contract → project → maintenance)
- Examples: `backend/database.py:24-260`
- Pattern: SQLAlchemy 2.0 `Mapped`/`mapped_column` typing; UUID primary keys (`uuid4` default); string-based `enum.Enum` subclasses for statuses; JSON columns for lists/dicts

## Entry Points

**None exist.** No FastAPI app, no `main.py`, no CLI, no scheduler, no test runner entry. `pyproject.toml` declares `fastapi`/`uvicorn` dependencies (`pyproject.toml:8-9`) and the README path (`pyproject.toml:5` references a `README.md` that does not exist), but there is no runnable process. Agents are only invocable by direct Python import.

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

**What happens:** LLM failures return the string `"ERROR: No LLM API key configured"` or `f"ERROR: {str(e)}"` as the "content" (`backend/agents/base.py:63,66`), indistinguishable from a legitimate LLM response.
**Why it's wrong:** Downstream JSON parsing or decision logic can treat an error string as real model output.
**Do this instead:** Raise typed exceptions or return a distinct error shape in the `{"success": False, ...}` result convention.

### Keyword-matching dispatch

**What happens:** `execute()` routes tasks by substring checks on the raw task text (`backend/agents/ceo.py:41-48`, `backend/agents/lead_hunter.py:50-55`).
**Why it's wrong:** Ambiguous or compound tasks ("approve proposal AND set strategy") match the first branch; keyword drift silently changes behavior.
**Do this instead:** Explicit task types/enums or structured task payloads with a `task_type` field.

### Bare `except: pass` in JSON parsing

**What happens:** `LLMAgent.execute` silently swallows all JSON parse failures (`backend/agents/base.py:169-170`) and falls back to raw text.
**Why it's wrong:** Malformed structured output is hidden; no logging or retry.
**Do this instead:** Log the failure, record `"parse_failed": True` in the result, and optionally retry with a correction prompt.

### Unwired persistence

**What happens:** Full ORM schema exists (`backend/database.py`) but nothing calls `init_db()` or imports the models; agents return mock/placeholder data instead.
**Why it's wrong:** Schema and runtime behavior can drift apart before integration.
**Do this instead:** Wire `init_db()` into a lifecycle hook (FastAPI lifespan, scheduler startup) and have agents persist through repositories.

## Error Handling

**Strategy:** Graceful degradation to error strings + boolean result flags; no exception propagation design yet.

**Patterns:**
- `call_llm` wraps the entire provider dispatch in `try/except` and logs via `logger.error(f"LLM call failed for {self.name}: {e}")` (`backend/agents/base.py:64-66`)
- `LLMAgent.execute` returns `{"success": True, ...}` with whatever it got — including error strings
- Role-base methods raise `NotImplementedError` to signal unimplemented contracts (`backend/agents/base.py:181-249`)
- `CEOAgent._review_proposal` returns `{"success": False, "error": "No proposal ID in context"}` for missing context (`backend/agents/ceo.py:58-59`)
- `NegotiationAgent.check_guardrails` returns `{"allowed": False, "min_price": ..., "reason": "..."}` for guardrail violations (`backend/agents/base.py:219-223`)

## Cross-Cutting Concerns

**Logging:** `loguru` logger; agent lifecycle logged in `run()` (`backend/agents/base.py:139,141`) and LLM failures logged in `call_llm` (`backend/agents/base.py:65`); no logging config file exists
**Validation:** Pydantic validation on `Settings` only; no Pydantic schemas for agent inputs/outputs — dicts are unchecked
**Authentication:** None implemented; `python-jose` and `passlib` declared in `pyproject.toml:29-30` but unused
**Configuration:** Single env-driven `Settings` with defaults; `.env.example` present at repo root (contains environment configuration template)
**Secrets:** All keys flow through `settings` from env vars (`backend/config.py`); API keys never hardcoded in source

---

*Architecture analysis: 2026-08-04*
