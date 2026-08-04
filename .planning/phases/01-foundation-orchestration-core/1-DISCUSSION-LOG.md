# Phase 1: Foundation & Orchestration Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-04
**Phase:** 1-Foundation & Orchestration Core
**Areas discussed:** Package layout & dependencies; Database & migrations; Audit log; Approval engine; Budget caps; Scheduler; Compliance middleware; Auth & Phase 1 UI; Observability & quality; Mock mode
**Mode:** auto (auto-advance chain from new-project, `_auto_chain_active=true`, `discuss_mode=discuss`)

---

## Package Layout & Dependencies (FND-01, FND-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Flat layout (`backend/` package, delete `src/`) | Single installable package; add `__init__.py`; `pip install -e .` | ✓ |
| Keep `src/` + `backend/` dual layout | Preserves existing scaffold, adds ambiguity | |

**User's choice:** Flat layout — `backend/` is the single package, `src/` deleted (matches CONCERNS + STACK findings).
**Notes:** uv lockfile committed; `sqlalchemy` declared (currently undeclared gap); README.md created (referenced by pyproject but missing).

## Dependency Version Strategy (FND-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Bump to research-verified current versions | Per STACK.md research table (FastAPI 0.141.1, redis 8.1.0, langgraph 1.2.10, etc.) | ✓ |
| Minimal bump (only what's broken) | Leaves staleness and known CVEs | |

**User's choice:** Bump to research-verified current versions.
**Notes:** Remove unused deps (playwright, stripe, razorpay, sendgrid, openai, python-jose, passlib, python-dotenv) — re-add in consuming phase. Replaces passlib/python-jose with pwdlib[argon2]/PyJWT/itsdangerous per research.

## Database & Migrations (FND-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic migrations, fix init ordering | Replace `create_all`, fix `get_db` TypeError, fail-fast on missing DATABASE_URL | ✓ |
| Keep `create_all` | Faster to start, no migration history | |

**User's choice:** Alembic.
**Notes:** Money fields float → Decimal (Numeric(12,2)) per ARCHITECTURE anti-pattern note.

## Audit Log (FND-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Append-only table + single AuditService | No UPDATE/DELETE, correlation_id for lead/proposal/contract trails | ✓ |
| Log-only (files) | No queryability | |

**User's choice:** Append-only DB table with AuditService.
**Notes:** timezone-aware timestamps; `datetime.utcnow` deprecated warning fixed.

## Approval Engine (FND-05)

| Option | Description | Selected |
|--------|-------------|----------|
| LangGraph 1.x new adoption | `interrupt()`/`Command(resume=...)` + `PostgresSaver` durable checkpoints; delete ancient 0.0.x pin/usage | ✓ |
| Defer LangGraph; DB-table + polling approval | Simpler, but contradicts research (orchestration capstone) | |

**User's choice:** LangGraph 1.x adoption now (research: API rewrite; 0.0.x is unusable).
**Notes:** `approval_requests` table for the queue UI; APScheduler sweeper for expiry/escalation; CEO fake auto-approval removed; round-trip proven with CEO/LeadHunter agents (success criterion 3).

## Budget Caps (FND-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Code-enforced at enforcement points | Hard-block cap-exceeding LLM calls/sends; audit + alert on breach | ✓ |
| LLM-prompted budgeting | Not reliable, violates guardrail-in-code principle | |

**User's choice:** Code-enforced at enforcement points.

## Scheduler (FND-07)

| Option | Description | Selected |
|--------|-------------|----------|
| APScheduler AsyncIOScheduler, enqueue-only + heartbeat | Per research (arq rejected — pins redis<6); jobs enqueue, don't run inline | ✓ |
| Celery | Heavyweight for single-owner scope | |

**User's choice:** APScheduler enqueue-only with heartbeat + alert on silent failure.

## Compliance Middleware (CMP-01..CMP-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Full middleware in foundation | robots.txt deny-by-default + TTL cache, per-domain token-bucket + jitter, anti-spam caps, consent records + suppression list + one-click unsubscribe endpoint | ✓ |
| Minimal (robots + rate limits only) | Defers anti-spam; risk since sending lands Phase 3 | |

**User's choice:** Full compliance middleware in foundation (release blocker per PITFALLS research).
**Notes:** Applied at single choke points (HTTP client factory + send service) so no path bypasses.

## Auth & Phase 1 UI (DASH-01, DASH-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Session auth (single owner) + minimal server-rendered UI | Signed HttpOnly cookie (itsdangerous), pwdlib[argon2]; login + approval queue via Jinja2 | ✓ |
| Full Next.js frontend now | Adds build complexity to a 2-page scope; dashboard real scope is Phase 2 | |

**User's choice:** Session auth + minimal server-rendered Phase 1 UI; Next.js 16 frontend deferred to Phase 2.

## Observability & Quality

| Option | Description | Selected |
|--------|-------------|----------|
| loguru sink + secret redaction + GitHub Actions CI (ruff → black → mypy → pytest) | Baseline tests incl. approval round-trip | ✓ |
| No CI in Phase 1 | Faster, but quality gates untested | |

**User's choice:** loguru redaction + CI in Phase 1.
**Notes:** Gemini key moved from URL query to headers (CONCERNS).

## Mock Mode

| Option | Description | Selected |
|--------|-------------|----------|
| MOCK_MODE env gate (dev only, default off); remove CEO auto-approval | Clean prod path; mock data isolated | ✓ |
| Keep mock path as-is | Leaves fake approval + hardcoded data in prod path | |

**User's choice:** MOCK_MODE gate, default off, auto-approval removed.

## Claude's Discretion

Queue page UX details, scheduler cadences, alert wiring (log-based for now), file naming, minor structural choices.

## Deferred Ideas

- Playwright crawl engine → Phase 2; Next.js 16 dashboard → Phase 2; Stripe/Razorpay + webhook idempotency → Phase 4; pgvector → Phase 2; Sentry/alert channels → Phase 6.
