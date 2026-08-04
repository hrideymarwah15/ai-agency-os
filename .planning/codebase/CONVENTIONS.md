# Coding Conventions

**Analysis Date:** 2026-08-04

## Naming Patterns

**Files:**
- All Python files are lowercase `snake_case.py`: `backend/config.py`, `backend/database.py`, `backend/agents/base.py`, `backend/agents/ceo.py`, `backend/agents/lead_hunter.py`
- Files containing a primary class use the class's role, not the class name: `ceo.py` contains `CEOAgent`, `lead_hunter.py` contains `LeadHunterAgent`

**Classes:**
- PascalCase: `Settings` (`backend/config.py:8`), `BaseAgent` (`backend/agents/base.py:25`), `CEOAgent` (`backend/agents/ceo.py:7`), `LeadHunterAgent` (`backend/agents/lead_hunter.py:10`), `AgentContext` (`backend/agents/base.py:15`), `Business`, `Audit`, `Proposal` (`backend/database.py:89,121,144`)
- Enums are PascalCase with UPPER_SNAKE members: `class BusinessStatus(str, enum.Enum)` with `DISCOVERED`, `CLOSED_WON` (`backend/database.py:24-31`)
- Abstract role bases use role noun + `Agent`: `DiscoveryAgent`, `AuditAgent`, `SalesAgent`, `NegotiationAgent`, `DeliveryAgent`, `OpsAgent` (`backend/agents/base.py:176-250`)

**Functions/Methods:**
- snake_case: `get_settings`, `init_db`, `get_db`, `close_db` (`backend/config.py:177`, `backend/database.py:270-303`)
- Private/internal methods prefixed with single underscore: `_call_openrouter`, `_call_groq`, `_call_gemini` (`backend/agents/base.py:68-108`), `_review_proposal`, `_handle_escalation`, `_set_strategy`, `_review_kpis` (`backend/agents/ceo.py:56-102`), `_discover_leads`, `_enrich_lead` (`backend/agents/lead_hunter.py:61,73`)
- Abstract methods declared with `@abstractmethod` and `pass` body: `get_default_system_prompt`, `execute` (`backend/agents/base.py:35-43`)

**Variables:**
- snake_case: `business_id`, `proposal_id`, `mock_leads`, `supabase_client` (`backend/agents/base.py:17-22`, `backend/agents/lead_hunter.py:70`, `backend/database.py:267`)
- Module-level mutable globals are lowercase: `engine`, `async_session_maker`, `supabase_client` (`backend/database.py:265-267`)
- Config field names are snake_case with UPPER_SNAKE env-var aliases: `agency_name: str = Field(default="Nexus AI Agency", alias="AGENCY_NAME")` (`backend/config.py:12`)

**Types:**
- Type hints are built from `typing` generics: `Dict[str, Any]`, `List[Dict]`, `Optional[str]`, `AsyncGenerator`
- Imports use direct member imports: `from typing import Dict, List, Optional, Any, AsyncGenerator` (`backend/agents/base.py:6`)
- `Optional[X]` used for nullable fields and optional parameters; never bare `X = None` without annotation

## Code Style

**Formatting:**
- Tool: black, configured in `[tool.black]` (`pyproject.toml:47-49`)
- Line length: 100 (`line-length = 100`)
- Target: Python 3.11 (`target-version = ['py311']`)
- 4-space indentation; 2 blank lines between top-level classes/functions; 1 blank line between methods
- **Status note:** the codebase is NOT currently black-formatted — 49 lines across the 5 Python files exceed 100 characters (17 in `backend/config.py`, 24 in `backend/database.py`, 4 in `backend/agents/base.py`, 2 in `backend/agents/ceo.py`, 2 in `backend/agents/lead_hunter.py`). Run `black backend/` before adding new code.
- Trailing whitespace exists on blank lines inside class bodies (e.g. `backend/config.py:9-10`); `black`/`ruff` would clean this

**Linting:**
- Tool: ruff, configured in `[tool.ruff]` (`pyproject.toml:51-53`)
- Line length: 100; target: py311
- No explicit rule selection — defaults apply
- Ruff would flag existing issues: unused imports (`os`, `asyncio`, `AsyncGenerator` in `backend/agents/base.py:2-6`; `json`, `asyncio` in `backend/agents/lead_hunter.py:2-3`; `List`, `Optional` in `backend/config.py:3`), bare `except:` at `backend/agents/base.py:169` (E722), out-of-order import `import enum` at `backend/database.py:14` (E402/I001)

## Import Organization

**Order:**
1. Standard library (stdlib first): `import asyncio`, `from datetime import datetime`, `from typing import ...`
2. Third-party (blank line after stdlib): `from loguru import logger`, `from pydantic import Field`, `from supabase import create_client, Client`, `from sqlalchemy...`
3. Local package (blank line after third-party): `from backend.config import settings` (`backend/agents/base.py:11`), `from backend.agents.base import BaseAgent, AgentContext` (`backend/agents/ceo.py:3`)
4. Example of correct full ordering: `backend/agents/base.py:1-11`

**Path Aliases:**
- No `src`-layout or path aliases configured; imports are absolute from repo root using `backend.` prefix (`from backend.config import settings`, `from backend.agents.base import DiscoveryAgent, AgentContext`)
- Exception to stdlib-first order: `import enum` appears after the `backend.config` import at `backend/database.py:14` — do not replicate; keep stdlib together at the top

## Error Handling

**Patterns:**
- Broad `try/except Exception` around LLM calls; log via `logger.error` and return an error-string rather than raising: `logger.error(f"LLM call failed for {self.name}: {e}")` then `return f"ERROR: {str(e)}"` (`backend/agents/base.py:64-66`)
- Result-envelope dicts for agent operations: `{"success": True, "data": ..., "raw": ...}` on success (`backend/agents/base.py:168-172`) and `{"success": False, "error": "No proposal ID in context"}` on failure (`backend/agents/ceo.py:59`)
- `raise NotImplementedError` marks unimplemented interface methods on specialized base agents (`backend/agents/base.py:181,185,193,197,205,209,217,231,235,239,247,251`)
- HTTP status handling via `response.raise_for_status()` on httpx responses (`backend/agents/base.py:86,105,124`); exceptions propagate to the caller's `except Exception`
- Bare `except: pass` around JSON parsing of LLM output (`backend/agents/base.py:169`) — prefer `except (ValueError, TypeError)` or log the failure instead
- Guard clauses return early with an error envelope before doing work (`backend/agents/ceo.py:58-59`)

**Rule for new code:** follow the envelope pattern for agent results; raise `NotImplementedError` for intentionally unimplemented interface methods; do not introduce new bare `except:` clauses.

## Logging

**Framework:** loguru (`from loguru import logger` in `backend/agents/base.py:9`; `loguru>=0.7.0` in `pyproject.toml:27`)

**Patterns:**
- Logging is used only in `backend/agents/base.py` — the three existing call sites are the convention:
  - `logger.info(f"[{self.name}] Starting task: {task[:100]}...")` before execution (`backend/agents/base.py:139`)
  - `logger.info(f"[{self.name}] Completed task")` after execution (`backend/agents/base.py:141`)
  - `logger.error(f"LLM call failed for {self.name}: {e}")` on failure (`backend/agents/base.py:65`)
- Log messages use f-strings with `[AgentName]` prefixes and truncate long inputs (`task[:100]`)
- `backend/config.py`, `backend/database.py`, `backend/agents/ceo.py`, `backend/agents/lead_hunter.py` contain no logging
- No `logger.add(...)` sink configuration anywhere; loguru defaults apply
- `print()` is not used anywhere in the codebase

## Comments

**When to Comment:**
- Section banners with `# ====` separators group related declarations in `backend/database.py:21-23, 86-88, 262-264`
- Inline trailing comments document column semantics on SQLAlchemy models: `# DESIGN, FRONTEND, BACKEND, TESTING, DEVOPS` (`backend/database.py:214`), `# Agent name` (`backend/database.py:216`), `# SENT, DELIVERED, OPENED, REPLIED, BOUNCED` (`backend/database.py:257`)
- Placeholder comments mark known-skeleton code: `# In production, this would call actual APIs` (`backend/agents/ceo.py:61`, `backend/agents/lead_hunter.py:68`), `# Implementation would use actual APIs` (`backend/agents/lead_hunter.py:116`), `# Last 10 exchanges` (`backend/agents/base.py:132`)
- Config section comments group settings: `# Agency Identity`, `# Database`, `# AI Providers` (`backend/config.py:11-30`)
- No TODO/FIXME/HACK comments exist in the codebase (the only `TODO` matches are the `TaskStatus.TODO` enum member, `backend/database.py:79`)

**Docstrings:**
- Every module has a one-line module docstring: `"""Core configuration module for AI Agency OS."""` (`backend/config.py:1`), `"""Database connection and models for AI Agency OS."""` (`backend/database.py:1`)
- Every class has a one-line class docstring: `"""Application settings loaded from environment variables."""` (`backend/config.py:9`), `"""Abstract base class for all agency agents."""` (`backend/agents/base.py:26`)
- Public methods have one-line docstrings: `"""Get cached settings instance."""` (`backend/config.py:178`), `"""Execute a task with the given context."""` (`backend/agents/base.py:42`)
- Abstract method bodies are a docstring followed by `pass` (`backend/agents/base.py:35-38`)
- Docstring style is plain triple-quoted one-liners — no Google/NumPy/Sphinx sections, no parameter/return annotations in docstrings (signatures carry that via type hints)
- Gaps: `set_context` and `register_tool` lack docstrings (`backend/agents/base.py:45-49`), as do all `__init__` methods — give new public methods a one-line docstring

## Function Design

**Size:** Methods are small and single-purpose; the largest classes compose small handlers (e.g. `CEOAgent.execute` dispatches to `_review_proposal`/`_handle_escalation`/`_set_strategy`/`_review_kpis`, `backend/agents/ceo.py:36-54`). System prompts are the only large string literals and are f-strings in `get_default_system_prompt` (`backend/agents/lead_hunter.py:13-44`).

**Parameters:**
- Every parameter is type-annotated — required by mypy `disallow_untyped_defs` (`pyproject.toml:58`)
- Optional parameters use `Optional[X] = None` defaults: `def __init__(self, name: str, model: Optional[str] = None, system_prompt: Optional[str] = None)` (`backend/agents/base.py:28`)
- Numeric defaults inline: `temperature: float = 0.7`, `max_tokens: int = 4000` (`backend/agents/base.py:51`), `limit: int = 10` (`backend/agents/base.py:179`)

**Return Values:**
- Every function declares a return type — required by mypy `warn_return_any` (`pyproject.toml:57`)
- Agent execution returns the `Dict[str, Any]` envelope `{"success": bool, "data": ..., "raw": ...}` (`backend/agents/base.py:168-172`)
- LLM calls return `str`; DB session getters return `AsyncSession` (`backend/database.py:293`); possibly-missing singletons return `Optional[Client]` (`backend/database.py:306`)
- Module lifecycle functions are `async def` and return `None`: `init_db`, `close_db` (`backend/database.py:270,299`)

**Async convention:** I/O-bound work is `async def` throughout (`execute`, `call_llm`, `init_db`, `get_db`); only pure helpers like `check_guardrails` (`backend/agents/base.py:219`) and `build_messages` (`backend/agents/base.py:127`) are sync.

## Module Design

**Exports:**
- `backend/config.py` exports class `Settings` plus an instantiated module-level singleton: `settings = get_settings()` (`backend/config.py:183`); `get_settings` is memoized with `@lru_cache()` (`backend/config.py:176-179`)
- `backend/database.py` exports SQLAlchemy `Base`, status enums, models, lifecycle functions (`init_db`, `get_db`, `close_db`, `get_supabase`), and module-level globals `engine`/`async_session_maker`/`supabase_client` (`backend/database.py:265-267`)
- `backend/agents/base.py` exports `AgentContext` dataclass and agent base classes; `ceo.py`/`lead_hunter.py` export concrete agents
- No `__init__.py` exists in `backend/` or `backend/agents/` — there are no barrel files; imports reference modules directly (`from backend.agents.base import ...`)
- Empty placeholder directories with no code: `backend/tools/`, `backend/workflows/`, `src/` (with `agents/`, `api/`, `core/`, `services/`, `workflows/` subdirs), `automations/`, `config/`, `deploy/`, `docs/`, `frontend/`, `scripts/`, `tests/`

**Pattern:** module-per-responsibility — settings in `config.py`, persistence in `database.py`, agent contract in `agents/base.py`, one concrete agent family per file.

---

*Convention analysis: 2026-08-04*
