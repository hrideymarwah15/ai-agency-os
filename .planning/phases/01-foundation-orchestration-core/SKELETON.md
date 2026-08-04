# Walking Skeleton — AI Agency OS

**Phase:** 1
**Generated:** 2026-08-05

## Capability Proven End-to-End

A signed-in owner can install the backend from a clean checkout (`uv sync`), run
`alembic upgrade head` against local PostgreSQL, start the API
(`uv run uvicorn backend.main:app`), log in with email + password, and see a
database-backed page (`/audit`) listing audit entries — including the audit row
the app itself wrote when the owner logged in. One install, one boot, one auth
round-trip, one real DB write (login → `audit_logs`) and one real DB read
(`/audit` → `audit_logs`).

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | FastAPI 0.141 + uvicorn, `@asynccontextmanager` lifespan, Jinja2 server-rendered UI | D-17 locks SSR (login/queue/audit/unsubscribe); lifespan replaces deprecated `on_event`; declared + research-verified (RESEARCH §Standard Stack) |
| Data layer | PostgreSQL 15 + SQLAlchemy 2.0 async (asyncpg) + Alembic 1.18 (replaces `create_all`, D-05); LangGraph checkpoints via `AsyncPostgresSaver` (psycopg 3 — a second, independent pool) | Single source of truth for schema; async-only runtime convention; research Pitfall 3 |
| Auth | itsdangerous `URLSafeTimedSerializer` signed cookie (HttpOnly/Secure/SameSite=Lax) + pwdlib `PasswordHash.recommended()` (Argon2id); single owner from env | D-16; zero DB reads per request, tamper-proof, expiring; passlib is unmaintained |
| Deployment target | Local dev: `uv` + uvicorn + Homebrew/docker-compose Postgres; GitHub Actions CI (ruff → black --check → mypy → pytest, D-19) | Free-tier solo operation; CI replicates fresh-venv install smoke |
| Directory layout | Flat `backend/` installable package; `api/`, `services/`, `auth/`, `workflows/`, `tools/`, `templates/`, `static/`, `alembic/` under it; models stay in `backend/database.py` | D-01 flat layout; FND-01; env.py imports `backend.database.Base` for autogen |

## Stack Touched in Phase 1

- [x] Project scaffold — pyproject.toml (current deps, `packages.find`, pytest config), `uv.lock`, README, .gitignore, `__init__.py` files
- [x] Routing — FastAPI app with `/health`, `/auth/login`, `/auth/logout`, `/audit` (later: `/approvals`, `/unsubscribe`)
- [x] Database — one real write (login audit event) AND one real read (`GET /audit` lists `audit_logs` rows)
- [x] UI — login form wired to `POST /auth/login` (sets session cookie, redirects to owner page)
- [x] Deployment — `uv run uvicorn backend.main:app` documented in README; `docker-compose.yml` for Postgres; CI smoke job (fresh venv → `pip install -e .` → `alembic upgrade head` → uvicorn boot)

## Out of Scope (Deferred to Later Slices)

- Approval queue UI / LangGraph engine (plan 03 of this phase)
- Full audit log filtering UI by correlation_id (plan 02 of this phase)
- Budget caps + scheduler (plan 04 of this phase) and compliance middleware (plan 05 of this phase)
- Real LLM calls (tests use `httpx.MockTransport`; `MOCK_MODE` gate, D-20), real lead discovery (Phase 2)
- Next.js 16 frontend, pgvector, outbox table, Redis-backed rate limiting, Sentry alerts

## Subsequent Slice Plan

Each later plan/phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Plan 02: full append-only audit trail — trigger, correlation_id query, audit page
- Plan 04: hard budget caps + heartbeat-monitored scheduler
- Plan 05: compliance middleware (robots, rate limits, consent/suppression, unsubscribe)
- Plan 03: LangGraph approval engine + owner approval queue (capstone)
- Phase 2: compliant lead discovery + pipeline view
- Phase 3: outreach + pricing + negotiation
- Phase 4: contracts + payments
- Phase 5: delivery; Phase 6: maintenance + growth
