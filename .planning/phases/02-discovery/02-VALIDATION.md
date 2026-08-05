---
phase: 02
slug: discovery
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-05
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | pyproject.toml ([tool.pytest.ini_options]) |
| **Quick run command** | `uv run pytest tests/test_discovery_*.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_discovery_*.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 02-PLAN | 1 | LEAD-01 | T-02-05 | api_hosts exemption audited once, deny-by-default preserved elsewhere | tdd | `uv run pytest tests/test_discovery_api_hosts.py tests/test_compliance.py -x -q` | plan | pending |
| 02-01-02 | 02-PLAN | 1 | LEAD-01 | — | Migration 0003 round-trips; models importable; flags default locked | auto | `uv run alembic upgrade head && uv run pytest tests/test_database.py -x -q && uv run alembic downgrade 0002 && uv run alembic upgrade head` | plan | pending |
| 02-01-03 | 02-PLAN | 1 | LEAD-05, DASH-02 | T-03-03 | Owner-guarded trigger+page; run/outbox/audit atomic with correlation_id | tdd | `uv run pytest tests/test_discovery_api.py -x -q` | plan | pending |
| 02-02-01 | 02-PLAN | 2 | CMP-06 | T-02-01 | Injection fixtures inert; caps enforced; never raises; tokens stripped | tdd | `uv run pytest tests/test_discovery_sanitize.py -x -q` | plan | pending |
| 02-02-02 | 02-PLAN | 2 | LEAD-01, LEAD-04 | — | 5 adapters per flags; reddit BLOCKED+audited zero requests; HN yields sanitized candidates | tdd | `uv run pytest tests/test_discovery_registry.py tests/test_discovery_exclusion.py tests/test_discovery_sources_hn.py -x -q` | plan | pending |
| 02-02-03 | 02-PLAN | 2 | LEAD-02, LEAD-03 | T-02-03 | 2 sources → 1 master + lineage; invalid URLs never fetched | tdd | `uv run pytest tests/test_discovery_normalize.py tests/test_discovery_dedup.py tests/test_discovery_enricher.py -x -q` | plan | pending |
| 02-02-04 | 02-PLAN | 2 | LEAD-05 | — | Invariants found==parsed+rejected, new+merged==parsed; 429→PARTIAL+BLOCKED+audit | tdd | `uv run pytest tests/test_discovery_run.py tests/test_discovery_worker.py -x -q` | plan | pending |
| 02-03-01 | 02-PLAN | 3 | LEAD-05 | — | Daily job enqueues run+outbox; heartbeat tests green | tdd | `uv run pytest tests/test_scheduler.py -x -q` | plan | pending |
| 02-03-02 | 02-PLAN | 3 | LEAD-02, DASH-02 | T-02-08 | Dashboard renders per-source stats, totals, dedup rate, lineage badges, coverage | tdd | `uv run pytest tests/test_discovery_api.py -x -q` | plan | pending |
