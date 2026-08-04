# AI Agency OS

An autonomous AI-powered digital agency platform: finds leads, qualifies prospects, generates
personalized outreach, negotiates within predefined limits, creates contracts, delivers
projects, collects payments, and manages clients with minimal human intervention. The owner
defines services, pricing rules, brand guidelines, legal templates, and approval limits; the
AI operates the rest — an AI company with specialized departments (agents) instead of a single
AI agent.

## Requirements

- Python 3.11+ (dev machine: 3.14.5)
- [uv](https://docs.astral.sh/uv/) (package manager; lockfile `uv.lock` is committed)
- PostgreSQL 15 — local (`brew services start postgresql@15` or `docker compose up -d`),
  Supabase, or any Postgres reachable via `DATABASE_URL`

## Install

```bash
uv sync --extra dev     # installs runtime deps + dev extras from the lockfile
```

## Configure

```bash
cp .env.example .env    # then edit values
```

Generate the owner password hash (Argon2id) and paste it into `OWNER_PASSWORD_HASH`:

```bash
uv run python scripts/hash_password.py hash
```

Required `.env` values: `DATABASE_URL`, `SESSION_SECRET`, `OWNER_EMAIL`,
`OWNER_PASSWORD_HASH`, `AGENCY_ADDRESS`. `.env` is gitignored — never commit it.

## Run

```bash
uv run uvicorn backend.main:app      # http://localhost:8000
```

Startup runs `alembic upgrade head` automatically (D-05). `GET /health` returns
`{"status": "ok"}` plus a DB ping.

## Migrate

Migrations replace `create_all` (FND-03):

```bash
uv run alembic upgrade head          # apply all migrations
uv run alembic revision --autogenerate -m "describe change"   # new migration
uv run alembic check                 # verify migrations are current (CI gate)
```

## Test

```bash
uv run pytest                        # full suite (needs ai_agency_os_test DB)
uv run pytest tests/ -x -q           # fast subset
```

Tests use a dedicated database `ai_agency_os_test` (created via `createdb`), migrated by
Alembic in a session fixture — never `create_all`.

## Lint & Typecheck

```bash
uv run ruff check .
uv run black --check .
uv run mypy backend/
```

## Project Layout

```
backend/          installable package (flat layout, D-01)
  api/            FastAPI routers (auth, audit, ...)
  auth/           session cookies + owner dependency (itsdangerous, D-16)
  services/       audit + budget + approval + compliance services
  templates/      Jinja2 pages (server-rendered UI, D-17)
  static/         app.css (UI-SPEC design tokens)
  alembic/        migrations (16 tables in 0001_initial)
tests/            pytest-asyncio suite (Wave 0 fixtures in conftest.py)
scripts/          hash_password.py (Argon2id hash for OWNER_PASSWORD_HASH)
```

## Docs

Planning artifacts live in `.planning/` (PROJECT.md, ROADMAP.md, phase plans, research,
patterns, UI-SPEC, validation strategy).
