"""Shared pytest fixtures for AI Agency OS — Wave 0 (1-VALIDATION.md §Wave 0)."""
import os
from pathlib import Path

import pytest

# ── Fixed test environment ──────────────────────────────────────────────
# Set at module import time so ANY backend import (collection or runtime)
# sees a stable, valid test environment. The autouse test_settings fixture
# rebuilds the settings singleton per test from this same env.
_TEST_ENV = {
    "DATABASE_URL": "postgresql://localhost:5432/ai_agency_os_test",
    "OWNER_EMAIL": "owner@test.local",
    "SESSION_SECRET": "test-session-secret",
    "SESSION_TTL_SECONDS": "43200",
    "COOKIE_SECURE": "false",
    "MOCK_MODE": "true",
    "AGENCY_ADDRESS": "1 Test Street, Test City",
    # Generous daily budgets so budget-gated code paths never trip in tests.
    "LLM_DAILY_BUDGET_USD_OPENROUTER": "1000",
    "LLM_DAILY_BUDGET_USD_GROQ": "1000",
    "LLM_DAILY_BUDGET_USD_GEMINI": "1000",
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)

# Known dev password whose Argon2id hash seeds OWNER_PASSWORD_HASH.
# pwdlib is a runtime dep declared in plan 01 Task 2a — the try/except keeps
# this module importable during the Wave 0 RED phase before pwdlib lands.
TEST_OWNER_PASSWORD = "test-password-123"
try:
    from pwdlib import PasswordHash

    _OWNER_HASH = PasswordHash.recommended().hash(TEST_OWNER_PASSWORD)
except ImportError:  # pragma: no cover — Wave 0 RED phase only
    _OWNER_HASH = ""
os.environ["OWNER_PASSWORD_HASH"] = _OWNER_HASH


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """Rebuild the settings singleton from the fixed test env for every test."""
    import backend.config as config_module

    for _key, _value in _TEST_ENV.items():
        monkeypatch.setenv(_key, _value)
    monkeypatch.setenv("OWNER_PASSWORD_HASH", _OWNER_HASH)
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings()
    yield


@pytest.fixture
async def test_engine():
    """Async engine bound to the dedicated test database."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        os.environ.get(
            "TEST_DATABASE_URL", "postgresql+asyncpg://localhost:5432/ai_agency_os_test"
        ),
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Async session bound to the test database."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.orm import AsyncSession

    maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture(scope="session")
def migrated_db():
    """Migrate the test database to head once per session (Alembic, not create_all)."""
    from alembic import command
    from alembic.config import Config

    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "backend" / "alembic"))
    command.upgrade(cfg, "head")
    yield cfg


@pytest.fixture
def in_memory_saver():
    """InMemorySaver checkpointer for LangGraph unit tests."""
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()


@pytest.fixture
async def pg_saver(migrated_db):
    """AsyncPostgresSaver bound to the test DB with setup() applied."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    dsn = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://localhost:5432/ai_agency_os_test"
    ).replace("+asyncpg", "")
    saver = await AsyncPostgresSaver.from_conn_string(dsn)
    await saver.setup()
    yield saver
    await saver.close()


@pytest.fixture
def mock_transport():
    """Factory building an httpx.AsyncClient with a canned-response transport."""
    import httpx

    def build(handler):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    return build
