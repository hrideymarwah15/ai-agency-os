# Codebase Structure

**Analysis Date:** 2026-08-04

## Directory Layout

```
ai-agency-os/
├── pyproject.toml            # Project metadata, deps, black/ruff/mypy config
├── .env.example              # Env var template (do not read/commit real .env)
├── backend/                  # All implemented Python code
│   ├── config.py             # Settings (pydantic-settings) — agency, DB, AI, pricing
│   ├── database.py           # SQLAlchemy models, enums, async engine, Supabase client
│   ├── agents/               # Agent hierarchy
│   │   ├── base.py           # BaseAgent ABC, AgentContext, LLMAgent, role bases
│   │   ├── ceo.py            # CEOAgent — strategy/approvals/escalation
│   │   └── lead_hunter.py    # LeadHunterAgent, MarketScannerAgent
│   ├── templates/            # Empty scaffolds (jinja2 planned)
│   │   ├── contracts/        # (empty)
│   │   ├── emails/           # (empty)
│   │   └── proposals/        # (empty)
│   ├── tools/                # (empty) — planned shared tools
│   └── workflows/            # (empty) — planned LangGraph workflows
├── src/                      # Empty scaffold (planned API/services/core)
│   ├── agents/               # (empty)
│   ├── api/                  # (empty)
│   ├── core/                 # (empty)
│   ├── services/             # (empty)
│   └── workflows/            # (empty)
├── frontend/                 # (empty) — planned Next.js app
├── tests/                    # (empty) — no tests yet
├── automations/              # (empty) — planned n8n/scripts
├── config/                   # (empty) — planned YAML/env configs
├── deploy/                   # (empty) — planned Docker/deploy configs
├── docs/                     # (empty) — planned documentation
├── scripts/                  # (empty) — planned utility scripts
└── .planning/                # Planning artifacts
    ├── legacy/               # PROJECT.md, ROADMAP.md (original planning)
    ├── specs/                # 20-section specs per department
    │   ├── core/             # SPEC-001-core-system-architecture.md
    │   ├── discovery/        # SPEC-002-lead-discovery-engine.md
    │   ├── sales/            # SPEC-003-sales-proposal-system.md
    │   ├── development/      # SPEC-004-development-pipeline.md
    │   └── (compliance, finance, growth, legal, maintenance,
    │        observability — empty category dirs)
    └── codebase/             # Codebase analysis documents (this file's home)
```

## Directory Purposes

**`backend/`:**
- Purpose: All implemented backend code — configuration, persistence, and agents
- Contains: `config.py`, `database.py`, `agents/`, `templates/`, `tools/`, `workflows/`
- Key files: `backend/config.py`, `backend/database.py`, `backend/agents/base.py`

**`backend/agents/`:**
- Purpose: Departmental AI agents built on the `BaseAgent` abstraction
- Contains: `base.py` (abstraction layer), `ceo.py`, `lead_hunter.py`
- Key files: `backend/agents/base.py` (read first — defines everything)

**`backend/templates/`:**
- Purpose: Planned Jinja2 templates for contracts, emails, and proposals
- Contains: three empty category subdirectories (`contracts/`, `emails/`, `proposals/`)
- Note: `jinja2` is already declared in `pyproject.toml:22`

**`backend/tools/` and `backend/workflows/`:**
- Purpose: Empty scaffolds for shared agent tools (per `BaseAgent.register_tool` at `backend/agents/base.py:48`) and LangGraph workflow graphs (`langgraph` declared at `pyproject.toml:17`)
- Contains: nothing yet

**`src/`:**
- Purpose: Empty scaffold mirroring the planned application split (`src/agents`, `src/api`, `src/core`, `src/services`, `src/workflows`); all current code lives under `backend/` instead — a decision point for future organization
- Contains: nothing yet

**`frontend/`, `tests/`, `automations/`, `config/`, `deploy/`, `docs/`, `scripts/`:**
- Purpose: Empty scaffold directories for the planned Next.js frontend, pytest suite (`pytest` in dev deps at `pyproject.toml:35-37`), n8n automations, deployment configs, documentation, and scripts
- Contains: nothing yet

**`.planning/legacy/`:**
- Purpose: Original project charter and roadmap
- Contains: `PROJECT.md` (vision, services, AI departments, tech stack), `ROADMAP.md` (8 milestones, 20+ phases)

**`.planning/specs/`:**
- Purpose: 20-section design specifications per department
- Contains: `core/SPEC-001-core-system-architecture.md`, `discovery/SPEC-002-lead-discovery-engine.md`, `sales/SPEC-003-sales-proposal-system.md`, `development/SPEC-004-development-pipeline.md`; empty category dirs: `compliance/`, `finance/`, `growth/`, `legal/`, `maintenance/`, `observability/`

**`.planning/codebase/`:**
- Purpose: Codebase analysis documents consumed by GSD planning/execution commands
- Contains: `ARCHITECTURE.md`, `STRUCTURE.md`

## Key File Locations

**Entry Points:**
- None. No `main.py`, no FastAPI app, no CLI, no scheduler. The closest to entry points are `BaseAgent.run()` (`backend/agents/base.py:137`) and `init_db()` (`backend/database.py:270`), both called only by direct import.

**Configuration:**
- `pyproject.toml`: project metadata, dependencies, black/ruff/mypy tool config (line-length 100, py311, `disallow_untyped_defs`)
- `backend/config.py`: runtime `Settings` — all env-var-backed configuration
- `.env.example`: env template at repo root (existence noted; contents not read)
- `.env`: loaded at runtime by `Settings.Config.env_file` (`backend/config.py:170`); must not be committed

**Core Logic:**
- `backend/agents/base.py`: `BaseAgent` ABC, `AgentContext`, `LLMAgent`, role bases (`DiscoveryAgent`, `AuditAgent`, `SalesAgent`, `NegotiationAgent`, `DeliveryAgent`, `OpsAgent`)
- `backend/agents/ceo.py`: `CEOAgent`
- `backend/agents/lead_hunter.py`: `LeadHunterAgent`, `MarketScannerAgent`
- `backend/database.py`: models and persistence wiring

**Data / Persistence:**
- `backend/database.py`: `Base`, `Business`, `Audit`, `Proposal`, `Contract`, `Project`, `Task`, `MaintenanceCheck`, `OutreachLog`; enums `BusinessStatus`, `ProposalStatus`, `ContractStatus`, `PaymentStatus`, `ProjectStatus`, `ServiceType`, `TaskStatus`; `init_db()`, `get_db()`, `close_db()`, `get_supabase()`

**Testing:**
- `tests/` exists but is empty; `pytest`, `pytest-asyncio`, `pytest-cov` are dev dependencies (`pyproject.toml:35-37`)

## Naming Conventions

**Files:**
- snake_case Python modules: `config.py`, `database.py`, `base.py`, `ceo.py`, `lead_hunter.py`
- UPPER_SNAKE spec files: `SPEC-001-core-system-architecture.md`

**Directories:**
- lowercase singular/plural nouns: `backend/agents/`, `backend/templates/`, `src/services/`, `.planning/specs/discovery/`

**Classes:**
- PascalCase, `Agent` suffix for agents: `BaseAgent`, `CEOAgent`, `LeadHunterAgent`, `MarketScannerAgent`, `LLMAgent`, `DiscoveryAgent`; `AgentContext` for context

**Enums:**
- PascalCase enum names, SCREAMING_SNAKE values: `BusinessStatus.DISCOVERED`, `ServiceType.WEBSITE`, `TaskStatus.BLOCKED` (`backend/database.py:24-84`)

**Settings fields / env aliases:**
- snake_case fields with UPPER_SNAKE env aliases: `max_discount_percentage` ↔ `MAX_DISCOUNT_PERCENTAGE` (`backend/config.py:85`); model assignments prefixed `model_*` (`backend/config.py:32-37`)

**Database:**
- Plural snake_case table names: `businesses`, `audits`, `proposals`, `contracts`, `projects`, `tasks`, `maintenance_checks`, `outreach_logs`; index prefix `ix_<table>_<column>` (e.g., `ix_businesses_status` at `backend/database.py:115`)

**Result dicts:**
- Uniform keys `success` / `data` / `raw` (optional `error`) across all agent results

## Where to Add New Code

**New agent (e.g., Sales, Auditor, Negotiation):**
- Primary code: new file `backend/agents/<name>.py`, subclassing the matching role base from `backend/agents/base.py` (e.g., `SalesAgent` → `backend/agents/sales.py`); implement `get_default_system_prompt()` and `execute()`, keep keyword dispatch and `{"success", "data", "raw"}` result shape
- Follow the model of `backend/agents/lead_hunter.py`

**New role base:**
- Add to the hierarchy in `backend/agents/base.py` next to the existing role bases (lines 176-251), following the `NotImplementedError` stub pattern

**New DB model:**
- Add to `backend/database.py` with `Mapped`/`mapped_column`, UUID PK, plural snake_case table name, and a status enum if applicable

**New config setting:**
- Add a field with env alias to `Settings` in `backend/config.py`, plus a matching entry in `.env.example`

**New template:**
- Place Jinja2 files under `backend/templates/<category>/` (`contracts/`, `emails/`, `proposals/`)

**New workflow (LangGraph):**
- `backend/workflows/` (adjacent to `backend/agents/`, consistent with current package layout)

**New API endpoint (planned FastAPI layer):**
- Decision point: `src/api/` scaffold exists, but current convention places all backend code under `backend/` — follow whichever is established when the API phase lands; the pattern in `.planning/specs/core/SPEC-001-core-system-architecture.md` describes an API gateway over the agent layer

**Tests:**
- `tests/`, mirroring `backend/` structure (`tests/agents/`, etc.); pytest + pytest-asyncio are already configured as dev deps

**Config / deploy / docs / scripts:**
- `config/` (YAML/env), `deploy/` (Docker), `docs/`, `scripts/` — empty and available

## Special Directories

**`src/`:**
- Purpose: Empty five-directory scaffold (`agents/`, `api/`, `core/`, `services/`, `workflows/`) that duplicates the `backend/` layout
- Generated: No
- Committed: Yes (empty dirs)
- Note: Ambiguity risk — new code could land in either `backend/` or `src/`; currently everything is in `backend/`

**`frontend/`:**
- Purpose: Planned Next.js 14 frontend (per `.planning/legacy/PROJECT.md`), not started
- Generated: No
- Committed: Yes (empty)

**`tests/`:**
- Purpose: Planned test suite; `pytest`/`pytest-asyncio`/`pytest-cov` dev deps declared but no tests exist
- Generated: No
- Committed: Yes (empty)

**`backend/templates/`:**
- Purpose: Template storage with per-category subdirectories (`contracts/`, `emails/`, `proposals/`); `jinja2` dependency declared but unused
- Generated: No
- Committed: Yes (empty subdirs)

**`backend/tools/`, `backend/workflows/`:**
- Purpose: Empty scaffolds for the tool registry and LangGraph orchestration layers planned in the specs
- Generated: No
- Committed: Yes (empty)

**`automations/`, `config/`, `deploy/`, `docs/`, `scripts/`:**
- Purpose: Empty scaffolds for n8n workflows, deployment, docs, and utility scripts
- Generated: No
- Committed: Yes (empty)

**`.planning/specs/` category dirs (`compliance/`, `finance/`, `growth/`, `legal/`, `maintenance/`, `observability/`):**
- Purpose: Placeholders for future department specs; only `core/`, `discovery/`, `sales/`, `development/` contain specs
- Generated: No
- Committed: Yes

**Git state:** Repo initialized with a `main` branch but zero commits; all files untracked as of this analysis.

---

*Structure analysis: 2026-08-04*
