# Technology Stack

**Analysis Date:** 2026-08-04

## Languages

**Primary:**
- Python >=3.11 (declared in `pyproject.toml` `requires-python`) — entire backend is Python. Dev machine runs Python 3.14.5. No runtime pin file (`.python-version`/`runtime.txt`) present.

**Secondary:**
- None in code. TypeScript/Next.js 14/React 18/Tailwind are specified in `.planning/legacy/PROJECT.md` and `.planning/specs/development/SPEC-004-development-pipeline.md` as the planned frontend stack for client deliverables, but `frontend/` is empty — no frontend code exists yet.

## Runtime

**Environment:**
- Python 3.11+ (no version manager pinning, no Dockerfile, no container config)

**Package Manager:**
- pip/setuptools via `pyproject.toml` (`[build-system]` requires setuptools>=68.0 + wheel)
- Lockfile: **missing** — no `requirements.txt`, `poetry.lock`, `uv.lock`, or `Pipfile` anywhere

## Frameworks

**Core:**
- FastAPI >=0.109.0 — declared in `pyproject.toml`, **not yet instantiated** (no app entry point, `backend/` has no `main.py`/`app.py`)
- Pydantic 2 >=2.5.0 + pydantic-settings >=2.1.0 — **actively used** in `backend/config.py` (Settings class)
- SQLAlchemy 2.0 async ORM (`sqlalchemy.ext.asyncio` + DeclarativeBase) — **actively used** in `backend/database.py`, but **NOT declared in `pyproject.toml`** (dependency gap — see CONCERNS)
- Uvicorn[standard] >=0.27.0 — declared, unused so far
- LangGraph >=0.0.30, langchain-core >=0.1.0, langchain-openai >=0.0.8 — declared; **agent code does NOT use them** — `backend/agents/base.py` calls LLM providers via raw `httpx.AsyncClient` instead
- Supabase >=2.3.0 (`supabase.create_client`) — actively used in `backend/database.py:290`

**Testing:**
- pytest >=7.4.0, pytest-asyncio >=0.23.0, pytest-cov >=4.1.0 — declared in `[project.optional-dependencies] dev`; `tests/` directory exists but is **empty** — no tests written yet

**Build/Dev:**
- black (line-length 100, target py311), ruff (line-length 100, target py311), mypy (`disallow_untyped_defs = true`, `warn_return_any = true`) — all configured in `pyproject.toml` tool sections

## Key Dependencies

**Critical (imported and exercised in code):**
- `pydantic` / `pydantic-settings` — config system, `backend/config.py:8`
- `supabase` — REST client for Supabase, `backend/database.py:7`
- `sqlalchemy` — async ORM engine/session/models, `backend/database.py:8` (undeclared dep)
- `asyncpg` — Postgres async driver (dialect string rewrite `postgresql://` → `postgresql+asyncpg://`, `backend/database.py:277`)
- `httpx` — all LLM provider calls (OpenRouter/Groq/Gemini), `backend/agents/base.py:54-125`
- `loguru` — logging, `backend/agents/base.py:9`

**Declared but not yet used in code:**
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

**Infrastructure:**
- `asyncpg` (DB driver), `supabase` (managed Postgres REST + auth client), `redis` (planned queue/cache — unused)

## Configuration

**Environment:**
- pydantic-settings `BaseSettings` with `env_file = ".env"`, `extra = "ignore"`, case-insensitive aliases — `backend/config.py:169-173`
- `.env.example` present (111 lines) documenting ~50 variables across 12 groups: agency identity, database, AI providers, model assignments, search/scraping, email/communications, WhatsApp, payments, deployment targets, monitoring, guardrails, Redis, scheduler
- `.env` itself: **not present** (only `.env.example`)
- Settings instance exported as module singleton `settings = get_settings()` with `lru_cache` — `backend/config.py:176-183`
- Hardcoded business data in config: service catalog dict (4 service types, 15 packages), industry multipliers (15 industries), size multipliers (5), urgency multipliers (4), condition multipliers (5) — `backend/config.py:98-167`

**Build:**
- `pyproject.toml` — single source of truth; `[tool.black]`, `[tool.ruff]`, `[tool.mypy]` sections
- No `setup.cfg`, `tox.ini`, `Makefile`, or CI config files

## Platform Requirements

**Development:**
- Python 3.11+ (dev machine: 3.14.5)
- Local Redis expected at `redis://localhost:6379/0` (default `REDIS_URL`)
- Local Ollama expected at `http://localhost:11434` (default `OLLAMA_BASE_URL`)
- Playwright browsers (once crawling is implemented)

**Production:**
- Nothing deployed; no Dockerfile, no docker-compose, no CI/CD config
- Planned targets (tokens configured in `backend/config.py:67-71`): Vercel, Cloudflare, Netlify; PROJECT.md also lists Railway/VPS
- Specs assume PostgreSQL + pgvector (`.planning/specs/core/SPEC-001-core-system-architecture.md`), Redis (Kafka mentioned as alternative in spec architecture diagram)

## Notes

- Git repo initialized on `main` with **zero commits** — entire codebase is untracked
- `README.md` referenced by `pyproject.toml` (`readme = "README.md"`) does not exist; no `.gitignore` present
- No `__init__.py` files exist anywhere — `backend.*` imports (`backend/config`, `backend/database`, `backend.agents.*`) resolve via implicit namespace packages only when running from repo root
- Backend structure is a skeleton: implemented files are `backend/config.py`, `backend/database.py`, `backend/agents/{base,ceo,lead_hunter}.py`; everything else (`backend/tools/`, `backend/workflows/`, `backend/templates/*/`, `src/*`, `automations/`, `config/`, `deploy/`, `scripts/`, `frontend/`, `tests/`, `docs/`) is empty scaffolding

---

*Stack analysis: 2026-08-04*
