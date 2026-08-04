---
phase: 01-foundation-orchestration-core
plan: 05
type: execute
subsystem: compliance
tags: [compliance, robots, rate-limit, send-gate, unsubscribe, anti-spam]
requires: [01-01, 01-02, 01-04]
provides: [CMP-01, CMP-02, CMP-03, CMP-04]
affects: [backend/main.py, backend/tools/, backend/services/compliance/, backend/api/, tests/]
tech-stack:
  added:
    - "urllib.robotparser (stdlib) — D-13 lock, deny-by-default with TTL cache"
    - "itsdangerous URLSafeTimedSerializer salt=\"unsubscribe\" — 7-day signed token"
  patterns:
    - "D-15 choke points: CompliantHTTPClient.fetch (robots → bucket → request) and check_send (consent → suppression → cap → address)"
    - "PostgreSQL ON CONFLICT DO NOTHING for idempotent suppression inserts"
key-files:
  created:
    - "backend/tools/http_client.py — CompliantHTTPClient, RobotsDeniedError, build_compliant_client() (D-15 door #1)"
    - "backend/services/compliance/robots.py — RobotsPolicy (deny-by-default, per-domain TTL cache, audit on default-deny)"
    - "backend/services/compliance/rate_limit.py — DomainTokenBucket (per-domain, jitter, refill=0 blocks forever)"
    - "backend/services/compliance/suppression.py — add/is_suppressed, case-insensitive normalization, idempotent"
    - "backend/services/compliance/consent.py — record_consent/has_consent with lawful basis + provenance"
    - "backend/services/compliance/send_gate.py — check_send (D-15 door #2)"
    - "backend/api/unsubscribe.py — public GET /unsubscribe?t=<signed 7-day token>"
    - "backend/templates/unsubscribe.html — success + invalid states (UI-SPEC copy)"
    - "backend/tools/__init__.py, backend/services/compliance/__init__.py — package markers"
    - "tests/test_compliance.py — 23 tests"
  modified:
    - "backend/main.py — mounts the public unsubscribe router"
decisions:
  - "Address check runs BEFORE the cap reserve in check_send: a blocked send must not consume a daily cap slot (plan listed cap then address; ordering refinement only, CMP-03 semantics preserved)"
  - "suppression.add is idempotent via ON CONFLICT DO NOTHING: a replayed unsubscribe link cannot 500 on the unique email constraint"
  - "RobotsPolicy deny-by-default catches (httpx.HTTPError, OSError, ValueError) — ruff BLE001 forbids blind except Exception; this covers the realistic fetch/parse failure surface and every such failure still denies + audits"
  - "unsubscribe.html extends base.html without the owner nav: the public page must not render the owner email/logout (contact_email passed under a separate variable)"
metrics:
  duration_minutes: 17
  tasks_completed: 3
  commits: 3
  tests_added: 23
  tests_total: 74
  completed: "2026-08-05"
---

# Phase 01 Plan 05: Compliance Middleware Summary

Compliance middleware: robots.txt deny-by-default with TTL cache, per-domain token-bucket rate limiting with jitter, the anti-spam send gate (consent records + lawful basis + suppression list + daily volume caps + physical address), and the public one-click unsubscribe endpoint with a signed 7-day token — all enforced at exactly two choke points (D-15): the compliant HTTP client factory and `check_send`.

## Objective

Every fetch path is compliant before it exists (Phase 2's crawler will use `build_compliant_client()`), and every future send (Phase 3) passes gates built now. Success criteria CMP-01..04 all met and test-proven.

## Tasks Executed

| # | Task | Commit |
|---|------|--------|
| 1 | Failing compliance tests — robots, bucket, gates, unsubscribe (RED) | `a73463c` |
| 2 | Compliance services + the single compliant fetch door (GREEN) | `15d52d7` |
| 3 | Send gate + one-click unsubscribe endpoint + page + wiring | `25245b1` |

## What Was Built

**D-15 door #1 — `backend/tools/http_client.py`:** `CompliantHTTPClient.fetch(url)` runs the pipeline in order: `RobotsPolicy.can_fetch(url)` → denied ⇒ `RobotsDeniedError` raised *before any request is issued* (T-05-01); then `DomainTokenBucket.acquire(hostname)`; then the httpx GET with `raise_for_status()`. `build_compliant_client()` wires settings (`crawler_user_agent`, `robots_cache_ttl_seconds`, `rate_limit_capacity/refill_per_sec`) with a module-shared bucket so all clients share per-domain limits.

**`robots.py`:** per-domain `urllib.robotparser.RobotFileParser`, robots.txt fetched once per domain through the inner client, TTL-cached. Any fetch/parse failure denies (CMP-01, T-05-05) with a `robots_denied_by_default` audit row (when a session is provided) — the TTL cache persists the deny so a broken robots.txt is never hammered.

**`rate_limit.py`:** the RESEARCH §Code Examples token bucket verbatim — monotonic-clock token math, per-domain isolation (CMP-02), uniform jitter `random.uniform(0, 1/refill)` on every wait. Refill=0 (a bucket that never recovers) blocks forever rather than dividing by zero.

**`suppression.py` / `consent.py`:** case-insensitive normalized CRUD against `suppression_entries` / `consent_records`. Suppression inserts are idempotent (`ON CONFLICT DO NOTHING`).

**D-15 door #2 — `send_gate.py`:** `check_send(session, *, email, channel)` returns `{"allowed": True}` only when consent exists, the recipient is not suppressed, a physical address is configured (CMP-04), and the atomic `reserve_outreach` cap (plan 04) does not raise `BudgetExceededError` (CMP-03, T-05-03). Every block returns `{"allowed": False, "reason": consent_required|suppressed|daily_cap_exceeded|address_required}` and writes a `send_blocked` audit row with the reason.

**Unsubscribe (CMP-04, T-05-02):** public `GET /unsubscribe?t=<token>` — the signed `URLSafeTimedSerializer` token *is* the identity (no email parameter in the URL); 7-day TTL; `BadSignature`/`SignatureExpired` render the "Invalid or expired link" state with no DB write; a valid token inserts `reason="one-click-unsubscribe"` and audits `unsubscribed`. Renders card-layout success/invalid states with the exact UI-SPEC copy, extending base.html without the owner nav.

## Verification

- `uv run pytest tests/ -x -q` → **74 passed** (51 pre-existing + 23 new; zero network — MockTransport for the fetch pipeline, test Postgres for gates/unsubscribe)
- `uv run ruff check`, `uv run black --check`, `uv run mypy` → clean on all committed files
- Robots TTL is asserted observably (fetch counts), jitter via a loose `[1.0, 2.5)` bound, cap atomicity via the shared `reserve_outreach` counter
- Unsubscribe round-trip proven end-to-end: valid token → suppression row + audit → next `check_send` returns `"suppressed"`; tampered and 8-day-old (expired) tokens → invalid state, no suppression row; public route works with zero cookies

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Canned robots.txt in tests let everything through**
- **Found during:** Task 2 GREEN run
- **Issue:** `robotparser` matches rules in file order — `Allow: /` before `Disallow: /private` allows all paths, so the deny test failed.
- **Fix:** canned robots.txt is now Disallow-only; unlisted paths are allowed per standard robots.txt semantics (deny-by-default still applies to *failures*).
- **Files modified:** tests/test_compliance.py
- **Commit:** `15d52d7`

**2. [Rule 1 - Bug] Robots audit test counted rows across runs**
- **Found during:** Task 2 GREEN run
- **Issue:** `audit_logs` is append-only (plan 02 trigger) and not cleaned per test — repeated runs accumulated `robots_denied_by_default` rows and broke the `len == 1` assertion.
- **Fix:** test uses a unique hostname per run and scopes the audit query by `entity_id`.
- **Files modified:** tests/test_compliance.py
- **Commit:** `15d52d7`

**3. [Rule 2 - Missing critical functionality] Replayed unsubscribe link could 500**
- **Found during:** Task 3 design
- **Issue:** plain `session.add` on a second unsubscribe for the same email violates the `suppression_entries.email` unique constraint → IntegrityError → 500 on the public route.
- **Fix:** `suppression.add` uses PostgreSQL `ON CONFLICT DO NOTHING` — idempotent, atomic, replay-safe.
- **Files modified:** backend/services/compliance/suppression.py
- **Commit:** `15d52d7`

**4. [Rule 3 - Blocking] ruff BLE001 rejected the blind `except Exception` in the deny-by-default path**
- **Found during:** Task 2 lint pass
- **Issue:** ruff 0.16.1 enforces flake8-blind-except; the robots policy must deny on any fetch/parse failure.
- **Fix:** scoped to `(httpx.HTTPError, OSError, ValueError)` — covers connection errors, HTTP status errors, transport failures, and parse errors; every failure still denies + audits.
- **Files modified:** backend/services/compliance/robots.py
- **Commit:** `15d52d7`

### Task-Boundary Adjustment

- **`send_gate.py` implemented in Task 2's commit** (plan listed it under Task 3): the Task 1 tests import `check_send` at module level, so test collection fails until it exists. Task 3's commit then delivered exactly what the plan scoped there (unsubscribe endpoint + template + main.py wiring). No behavior change; commit boundaries are noted in the table above.

## TDD Gate Compliance

- RED gate: `a73463c` `test(01-05): add failing compliance tests...` — collection failed with `ModuleNotFoundError` before any implementation.
- GREEN gate: `15d52d7` `feat(01-05): compliance services + single compliant fetch door` — 20 of 23 tests green (unsubscribe needed Task 3), full suite green at `25245b1`.
- REFACTOR gate: no refactor commit — none needed (black/ruff/mypy clean from the start of the GREEN pass).

## Auth Gates

None — unattended run completed without any human-in-the-loop gate.

## Known Stubs

None. `build_compliant_client()`'s robots-audit session seam defaults to `None` in the fetch pipeline (no session available there by design); the audit fires when a session is provided — documented in code.

## Threat Surface

No new surface beyond the plan's threat model. The `/unsubscribe` public mutation endpoint is T-05-02 in the plan (token-gated, no email parameter, 7-day TTL, no existence-revealing responses).
