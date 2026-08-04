# Deferred Items — Phase 01 Plan 01 (Walking Skeleton)

Out-of-scope discoveries logged per executor scope boundary (do NOT fix here; resolved by later plans).

## 1. Legacy `backend/agents/*.py` lint/type debt (blocks CI ruff/black/mypy gates)

**Files:** `backend/agents/base.py`, `backend/agents/ceo.py`, `backend/agents/lead_hunter.py` (untracked pre-existing work, NOT part of plan 01-01 commits)

**Issues (all pre-existing, not introduced by this plan):**
- `ruff check .` (CI ruff job): 90+ errors — I001 import sorting, F401 unused imports (os/json/asyncio), UP006/UP035 deprecated typing.Dict/List/Optional, UP045 `X | None`, E722 bare `except:`, S110 try-except-pass, F841 unused vars, DTZ003 `datetime.utcnow()`
- `black --check .` (CI black job): 3 files would be reformatted
- `mypy backend/` (CI mypy job): 14 errors (no-untyped-def, no-any-return, attr-defined, arg-type)

**Impact:** CI jobs `ruff`/`black`/`mypy` run repo-wide and will be RED until the agents code is reworked. Options for the agents plan (roadmap 01-02/01-03): run `ruff --fix` + black + fix mypy errors as part of that plan's first task, or add per-path ignores to pyproject.

**Note:** plan 01-01's own new/modified files are all ruff/black/mypy clean (verified).

## 2. StarletteDeprecationWarning: TestClient uses deprecated httpx integration

FastAPI 0.141's TestClient emits `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` — cosmetic, 1 warning in the suite. No action needed this plan; revisit when starlette/httpx2 stabilizes.

## 3. `alembic check` vs langgraph checkpointer tables

Resolved in-plan (env.py `include_object` skips `checkpoints`/`checkpoint_writes`/`checkpoint_blobs`/`checkpoint_migrations`). Future alembic autogenerates keep working because the callback lives in env.py. If langgraph ever adds new table names, extend `_LANGGRAPH_TABLES`.

## 4. Test DB partial-migration residue

`ai_agency_os_test` contained a stale partial migration (8 tables + `businessstatus` enum, no `alembic_version`) from a pre-plan-01 session run. Recreated via `dropdb`/`createdb` — disposable by design. No code change needed.
