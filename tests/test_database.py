"""Database lifecycle tests — RuntimeError guard, URL.create engine, tz-aware and callable defaults."""


import pytest

from backend.config import settings
from backend.database import Base, Business, DiscoveryRun, DiscoveryRunSourceStat, RunStatus


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


def test_all_nineteen_tables_in_metadata():
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
        "outbox_events",
        "discovery_runs",
        "discovery_run_source_stats",
        "business_source_records",
    }
    assert len(names) == 19
    assert expected.issubset(names)


def test_discovery_run_model_defaults():
    from backend.database import BusinessSourceRecord, SourceRunStatus

    run = DiscoveryRun(trigger_source="MANUAL", correlation_id="corr-1")
    assert run.correlation_id == "corr-1"
    status_default = DiscoveryRun.__table__.c.status.default.arg
    assert status_default == RunStatus.RUNNING

    stat_status_default = DiscoveryRunSourceStat.__table__.c.status.default.arg
    assert stat_status_default == SourceRunStatus.OK

    raw_default = BusinessSourceRecord.__table__.c.raw_payload.default.arg
    assert raw_default is not None


def test_business_dedup_key_columns_exist():
    assert Business.__table__.c.dedup_key_domain is not None
    assert Business.__table__.c.dedup_key_phone is not None
    assert Business.__table__.c.rating is not None
    assert Business.__table__.c.enrichment_version.default.arg == 1


def test_discovery_config_flags_locked_defaults():
    assert settings.source_hn_enabled is True
    assert settings.source_reddit_enabled is False
    assert settings.source_yelp_enabled is False
    assert settings.source_google_places_enabled is False
    assert settings.source_mock_directory_enabled is False
    assert settings.discovery_max_items_per_source == 50
    assert settings.yelp_api_key == ""
    assert settings.google_places_api_key == ""
