---
phase: 01-foundation-orchestration-core
plan: 01
subsystem: infra
tags: [fastapi, uvicorn, sqlalchemy, alembic, postgres, langgraph, asyncpg, argon2id, pwdlib, loguru, pytest, ruff, mypy, black, uv, ci, jinja2]

# Dependency graph
requires:
  - phase: 00-research
    provides: stack decision (FastAPI + SQLAlchemy async + PostgreSQL + langgraph), TDD mandate, D-01..D-18 decisions
provides:
  - production-grade walking skeleton: app boots via uv run, /health with DB ping, Alembic-managed async DB layer
  - owner login/logout (Argon2id password hash, signed session cookie) + owner-only audit log route
  - audit service recording owner_login/owner_logout rows with correlation IDs
  - UI-SPEC-conformant login/audit pages (Jinja2 autoescape, zero client-side JS)
  - repo-wide CI (ruff, black, mypy, pytest + alembic check, smoke) and hardened D-18-secured config
  - 22-test suite proving the skeleton end-to-end
affects: [01-02 agents, 01-03 messaging, later phases reusing main.py lifespan, alembic env, session/owner deps]

# Tech tracking
tech-stack:
  added: [fastapi, uvicorn, pydantic-settings, sqlalchemy[asyncio] 2.0.51, asyncpg, psycopg, alembic, langgraph, langgraph-checkpoint-postgres 3.x, pwdlib[argon2], itsdangerous, jinja2, loguru, pytest, pytest-asyncio, ruff, black, mypy, uv]
  patterns:
    - async SQLAlchemy session dependency (async_session_factory + get_session) for FastAPI routes
    - lifespan-driven initialization: init_db -> alembic upgrade head in background thread -> AsyncPostgresSaver (async context manager) setup
    - uniform auth failure responses + owner dependency (get_current_owner) raising 401, mapped to 302 /auth/login with flash cookie
    - INSERT-only AuditService.record with uuid4 correlation_id; listing via audit_entries table
    - loguru D-18 redaction sink using compiled secret regex before write
    - alembic env include_object callback excluding langgraph checkpointer tables from autogenerate

key-files:
  created:
    - backend/main.py (Task 2b + Task 3 final: lifespan, health, routers, static mount, 401 handler)
    - backend/database.py
    - backend/api/auth.py, backend/api/audit.py
    - backend/auth/session.py, backend/auth/owner.py
    - backend/services/audit.py
    - backend/templates/base.html, login.html, audit.html
    - backend/static/app.css
    - backend/alembic/env.py, versions/e565deca858e_initial_schema.py
    - scripts/hash_password.py
    - tests/conftest.py, tests/test_auth.py
    - .github/workflows/ci.yml
  modified:
    - backend/config.py, pyproject.toml, alembic.ini, .env.example

key-decisions:
  - "login.html requires agency_name in context — passed on GET and failed-POST renders (D-17)"
  - "uniform 'Invalid email or password.' failure; no user-existence disclosure (D-16)"
  - "session cookie: itsdangerous URLSafeTimedSerializer signed payload, HttpOnly/SameSite=Lax, max_age = SESSION_TTL_SECONDS (D-16)"
  - "401 handler redirects to /auth/login with session-expired flash (D-16)"
  - "password hashing deferred from plan (D-18) — applied Argon2id via pwdlib; OWNER_PASSWORD_HASH env var (D-16)"
  - "hash generation at runtime via test fixture (cached); scripts/hash_password.py for humans"
  - "aforementioned AsyncPostgresSaver async context manager usage (langgraph-checkpoint-postgres 3.x API) applied consistently"
  - "black/ruff reformat of alembic-generated migration files to satisfy CI gates"

patterns-established:
  - "async_lifespan pattern: init_db -> alembic upgrade head via asyncio.to_thread -> checkpointer setup"
  - "session/owner/auth layering: cookie signing (itsdangerous) -> owner dependency -> route guard"
  - "audit service: INSERT-only writer, chronological list_recent(50) for /audit"
  - "config override via env vars (no .env auto-load in CI); settings cached via get_settings"

requirements-completed: []

# Metrics
duration: 55min
completed: 2026-08-05
---

# Phase 01 Plan 01: Walking Skeleton — Summary

**Production-grade walking skeleton: Alembic-migrated async PostgreSQL layer, D-16/D-18-compliant Argon2id owner login with signed session cookies, owner-only audit log route with audit service, UI-SPEC login/audit pages, and a green 22-test suite plus repo-wide CI (ruff/black/mypy/pytest+alembic check/smoke)**

## Performance

- **Duration:** ~55 min (02:14 → 03:06 +0530)
- **Started:** 2026-08-05T20:44:00Z (session start)
- **Completed:** 2026-08-05T21:37:32Z
- **Tasks:** 2a (verified), 2b, 3 — all executed; 3 task commits + 1 docs commit
- **Files modified:** 19 committed in Task 3 + 8 in Task 2b (27 total changed)

## Accomplishments

- Repaired dependency set + hardened config (D-18 redaction, budgets, compliance, mock mode) — Task 2a verified via commit `454f9a8`
- Alembic async migration layer with full schema (16 tables incl. audit_entries + unique thread_id constraint), clean `alembic upgrade head` and `alembic check` (CI FND-03 gate green)
- App entry point with lifespan wiring: `init_db` → alembic upgrade in background thread → `AsyncPostgresSaver` setup → yield; `/health` pings DB
- Owner login/logout with Argon2id verification (`pwdlib`), uniform failure message, signed session cookie, 401→302 session-expired redirect, audit rows `owner_login`/`owner_logout` with correlation IDs
- `/audit` route rendering newest 50 entries per UI-SPEC (Jinja2 autoescape, zero client-side JS)
- `scripts/hash_password.py` for generating OWNER_PASSWORD_HASH
- End-to-end smoke passed: real login → audit row → /audit render
- 22 tests green (auth flow, config, database, audit); ruff/black/mypy clean on all plan-owned files

## Task Commits

Each task was committed atomically:

1. **Task 2a: repair deps + config + infra/CI** — `454f9a8` (feat; pre-existing commit verified — acceptance criteria met, no re-work needed)
2. **Task 2b: alembic migration + app entry point** — `96a511f` (feat)
3. **Task 3: owner login + audit route** — `7e248c8` (feat)

**Plan metadata:** (docs commit below)

_Note: Task 2a was already satisfied by the existing commit from the previous session; no new commit created._

## Files Created/Modified

- `backend/main.py` — lifespan (init_db → alembic upgrade → AsyncPostgresSaver setup), `/health` DB ping, router mounting, static/templates, D-18 redaction sink, 401 handler
- `backend/database.py` — async engine/session factory, `build_database_url`, `postgres_dsn`, 16-table schema incl. audit_entries
- `backend/api/auth.py` — GET/POST /auth/login, POST /auth/logout
- `backend/api/audit.py` — GET /audit (owner-guarded, newest 50)
- `backend/auth/session.py` — URLSafeTimedSerializer cookie signing, flash helpers
- `backend/auth/owner.py` — get_current_owner → 401
- `backend/services/audit.py` — INSERT-only AuditService + list_recent
- `backend/templates/base.html`, `login.html`, `audit.html` — UI-SPEC pages (autoescape on, no client JS)
- `backend/static/app.css` — UI-SPEC tokens + primitives (slate/blue palette, 400px card, badges, empty state)
- `backend/alembic/env.py` — async env + `include_object` skipping langgraph checkpointer tables
- `backend/alembic/versions/e565deca858e_initial_schema.py` — full initial schema
- `scripts/hash_password.py` — Argon2id hash generator
- `tests/conftest.py` — test env, migrated_db fixture, pg_saver async-CM fixture, test_session
- `tests/test_auth.py` — full auth flow tests
- `tests/test_config.py`, `tests/test_database.py` — config/D-18 + schema tests
- `pyproject.toml`, `alembic.ini`, `.env.example`, `.github/workflows/ci.yml`, `backend/config.py` — infra/config hardening

## Decisions Made

- **Task 2a verification:** existing commit `454f9a8` already satisfied all acceptance criteria (13 config/database tests green, `src/` deleted, removed-dep grep clean, 5 CI jobs) → no re-work
- **Login page context:** `agency_name` must be passed on both GET and failed-POST renders (template requires it) — applied to both paths
- **Uniform failure message:** "Invalid email or password." for all auth failures (no user-existence disclosure, D-16)
- **Cookie security:** HttpOnly, SameSite=Lax, max_age = SESSION_TTL_SECONDS, Secure per `cookie_secure` config
- **Argon2id via pwdlib** for password hashing (D-18) — hash regenerated per session in tests via fixture cache
- **Test DB strategy:** fresh `dropdb`/`createdb` of `ai_agency_os_test` to clear stale partial migration residue

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AsyncPostgresSaver usage (async context manager)**
- **Found during:** Task 2b (main.py lifespan)
- **Issue:** `AsyncPostgresSaver.from_conn_string()` in langgraph-checkpoint-postgres 3.x is an **async context manager**, not a plain awaitable — `await from_conn_string(...)` would fail at startup; `checkpointer.setup()` must run inside `async with`
- **Fix:** Wrapped as `async with AsyncPostgresSaver.from_conn_string(...) as cp: await cp.setup()`; patched same bug in `tests/conftest.py` pg_saver fixture
- **Files modified:** backend/main.py, tests/conftest.py
- **Verification:** App boots, smoke test passes, pg_saver tests green
- **Committed in:** 96a511f (Task 2b commit)

**2. [Rule 1 - Bug] AsyncSession import from sqlalchemy.orm**
- **Found during:** Task 2b (test_session fixture)
- **Issue:** `from sqlalchemy.orm import AsyncSession` is a 2.1-only re-export; project pinned to 2.0.51 → ImportError at fixture import
- **Fix:** Import from `sqlalchemy.ext.asyncio`
- **Files modified:** tests/conftest.py
- **Verification:** Full suite green
- **Committed in:** 7e248c8 (Task 3 commit)

**3. [Rule 1 - Bug] anyio.to_thread is a module**
- **Found during:** Task 3 (login argon2 verify)
- **Issue:** `anyio.to_thread(...)` was called as a function — mypy caught it (would have crashed logins at runtime)
- **Fix:** `await anyio.to_thread.run_sync(...)`
- **Files modified:** backend/api/auth.py
- **Verification:** Login smoke passed
- **Committed in:** 7e248c8

**4. [Rule 1 - Bug] config.py mypy gate failure**
- **Found during:** Task 2a verification (CI mypy job)
- **Issue:** `get_settings` cache assignment failing mypy on strict settings
- **Fix:** Corrected type annotation/assignment
- **Files modified:** backend/config.py
- **Verification:** `mypy backend/` clean on plan-owned files
- **Committed in:** 96a511f

**5. [Rule 3 - Blocking] alembic check gate failure (langgraph tables)**
- **Found during:** Task 3 verification (CI pytest job runs `alembic check` AFTER pytest)
- **Issue:** `alembic check` flagged langgraph checkpointer tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`) as extras
- **Fix:** `include_object` callback in `backend/alembic/env.py` skipping `_LANGGRAPH_TABLES`
- **Files modified:** backend/alembic/env.py
- **Verification:** `alembic check` → "No new upgrade operations detected."
- **Committed in:** 7e248c8

**6. [Rule 1 - Bug] Stale test DB partial migration**
- **Found during:** Task 3 (pytest failures)
- **Issue:** `ai_agency_os_test` had 8 tables + orphaned `businessstatus` enum but no `alembic_version` → migration/schema mismatch failures
- **Fix:** `dropdb`/`createdb` the disposable test DB
- **Files modified:** none (environment reset)
- **Verification:** 22/22 green, idempotent against fresh DB
- **Committed in:** (environment fix, no commit)

**7. [Rule 3 - Blocking] uv sync prunes dev deps**
- **Found during:** Task 3 (pytest spawn failure)
- **Issue:** `uv sync --frozen` without `--extra dev` removes pytest/ruff from venv → "Failed to spawn: pytest" (false alarm, not a real break)
- **Fix:** Always `uv sync --frozen --extra dev` before test runs
- **Files modified:** none (command usage)
- **Verification:** pytest spawns
- **Committed in:** (process fix, no commit)

**8. [Rule 3 - Blocking] loguru.Record only in .pyi (runtime NameError)**
- **Found during:** Task 3 (main.py redaction sink)
- **Issue:** `loguru.Record` is a TypedDict only available in `.pyi` — runtime NameError
- **Fix:** `from __future__ import annotations` + TYPE_CHECKING import of Record
- **Files modified:** backend/main.py
- **Verification:** Boot smoke passed
- **Committed in:** 7e248c8

**9. [Rule 2 - Missing Critical] TemplateResponse signature (FastAPI 0.141+ / Starlette)**
- **Found during:** Task 3 (login page render)
- **Issue:** positional `request` argument required; rendering with `context` keyword
- **Fix:** `templates.TemplateResponse(request, "login.html", context)` — signature applied consistently
- **Files modified:** backend/api/auth.py
- **Verification:** Login page renders in smoke
- **Committed in:** 7e248c8

**10. [Rule 3 - Blocking] CI gate formatting (black/ruff) on alembic-generated files**
- **Found during:** Task 3 verification
- **Issue:** black CI gate would fail on alembic-generated migration/env files (different formatting)
- **Fix:** black-formatted `env.py` + `e565deca858e_initial_schema.py`
- **Files modified:** backend/alembic/env.py, backend/alembic/versions/e565deca858e_initial_schema.py
- **Verification:** `black --check` clean on all plan-owned files
- **Committed in:** 7e248c8

---

**Total deviations:** 10 auto-fixed (6 Rule 1 bugs, 1 Rule 2 missing-critical, 3 Rule 3 blocking)
**Impact on plan:** All fixes necessary for correctness, CI gate compliance, or security. No scope creep; no architectural changes (no Rule 4).

## Issues Encountered

- **Session continuity:** Task 2a was pre-executed by the previous session; verified acceptance criteria + commit existence instead of re-implementing (no new commit)
- **Test DB residue:** stale partial migration from pre-plan-01 session runs; resolved via disposable-DB recreation
- **Dev `.env` placeholder hash:** OWNER_PASSWORD_HASH placeholder — CI/smoke use real hashes; humans use `scripts/hash_password.py`

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Ready:** walking skeleton boots, DB migrates cleanly, auth + audit routes live, CI green for plan-owned files, 22-test suite as regression net for agents work
- **Blockers for next phases:** legacy `backend/agents/*.py` (untracked) fails ruff/black/mypy — CI jobs run repo-wide and stay RED until the agents plan (01-02/01-03) reworks those files. Recommended first task of that plan: `ruff --fix` + black + mypy cleanup of agents files.
- See `deferred-items.md` in this phase directory for details.

---
*Phase: 01-foundation-orchestration-core*
*Completed: 2026-08-05*
