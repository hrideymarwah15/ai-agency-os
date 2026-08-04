"""Database lifecycle tests — RuntimeError guard, URL.create engine, tz-aware and callable defaults."""

import pytest

from backend.database import Base, Business


async def test_get_db_before_init_raises_runtime_error(monkeypatch):
    import backend.database as db_module

    monkeypatch.setattr(db_module, "async_session_maker", None)
    with pytest.raises(RuntimeError, match="Database not initialized"):
        async for _ in db_module.get_db():
            pass


def test_build_database_url_never_double_drivers():
    from backend.database import build_database_url

    plain = build_database_url("postgresql://localhost:5432/ai_agency_os_test")
    assert plain.drivername == "postgresql+asyncpg"

    already = build_database_url("postgresql+asyncpg://localhost:5432/ai_agency_os_test")
    assert already.drivername == "postgresql+asyncpg"
    assert "+asyncpg+asyncpg" not in str(already)


async def test_init_db_builds_asyncpg_engine(monkeypatch):
    import backend.database as db_module

    monkeypatch.setattr(
        db_module.settings, "database_url", "postgresql://localhost:5432/ai_agency_os_test"
    )
    await db_module.init_db()
    assert db_module.engine is not None
    assert db_module.engine.url.drivername == "postgresql+asyncpg"
    assert str(db_module.engine.url).count("+asyncpg") == 1
    await db_module.close_db()


def test_init_db_raises_when_database_url_empty(monkeypatch):
    import backend.database as db_module

    monkeypatch.setattr(db_module.settings, "database_url", "")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        import asyncio

        asyncio.run(db_module.init_db())


def test_datetime_defaults_are_tz_aware():
    default = Business.__table__.c.created_at.default.arg
    assert callable(default)
    value = default(None)
    assert value.tzinfo is not None
    assert value.tzinfo.utcoffset(value).total_seconds() == 0  # UTC


def test_json_columns_use_callable_defaults():
    default = Business.__table__.c.social_links.default.arg
    assert callable(default)
    assert default(None) == {}


def test_all_sixteen_tables_in_metadata():
    names = set(Base.metadata.tables.keys())
    expected = {
        "businesses",
        "audits",
        "proposals",
        "contracts",
        "projects",
        "tasks",
        "maintenance_checks",
        "outreach_logs",
        "audit_logs",
        "approval_requests",
        "llm_spend",
        "outreach_spend",
        "scheduler_heartbeats",
        "consent_records",
        "suppression_entries",
    }
    assert len(names) == 16
    assert expected.issubset(names)
