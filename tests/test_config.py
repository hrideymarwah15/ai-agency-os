"""Config validation tests — required identity fields fail fast, alias mapping, new sections."""
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.config import Settings

# Settings(_env_file=None) keeps tests hermetic: only os.environ drives the
# values (a developer .env must never leak into test expectations).


def _unset(monkeypatch, *names):
    for name in names:
        monkeypatch.delenv(name, raising=False)


def test_required_identity_fields_raise_when_unset(monkeypatch):
    _unset(monkeypatch, "OWNER_EMAIL", "OWNER_PASSWORD_HASH", "AGENCY_ADDRESS")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_owner_email_required(monkeypatch):
    _unset(monkeypatch, "OWNER_EMAIL")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_owner_password_hash_required(monkeypatch):
    _unset(monkeypatch, "OWNER_PASSWORD_HASH")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_agency_address_required(monkeypatch):
    _unset(monkeypatch, "AGENCY_ADDRESS")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_upper_snake_alias_mapping(monkeypatch):
    monkeypatch.setenv("AGENCY_NAME", "Alias Test Agency")
    monkeypatch.setenv("AGENCY_PHONE", "+1-555-0100")
    settings = Settings(_env_file=None)
    assert settings.agency_name == "Alias Test Agency"
    assert settings.agency_phone == "+1-555-0100"


def test_new_sections_parse(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "parse-secret")
    monkeypatch.setenv("SESSION_TTL_SECONDS", "7200")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD_OPENROUTER", "12.50")
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD_GROQ", "3.25")
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD_GEMINI", "1.75")
    monkeypatch.setenv("CRAWLER_USER_AGENT", "TestBot/1.0")
    monkeypatch.setenv("ROBOTS_CACHE_TTL_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_CAPACITY", "2.0")
    monkeypatch.setenv("RATE_LIMIT_REFILL_PER_SEC", "0.5")
    monkeypatch.setenv("MOCK_MODE", "true")
    settings = Settings(_env_file=None)
    assert settings.session_secret == "parse-secret"
    assert settings.session_ttl_seconds == 7200
    assert settings.cookie_secure is True
    assert settings.llm_daily_budget_usd_openrouter == Decimal("12.50")
    assert settings.llm_daily_budget_usd_groq == Decimal("3.25")
    assert settings.llm_daily_budget_usd_gemini == Decimal("1.75")
    assert settings.crawler_user_agent == "TestBot/1.0"
    assert settings.robots_cache_ttl_seconds == 60
    assert settings.rate_limit_capacity == 2.0
    assert settings.rate_limit_refill_per_sec == 0.5
    assert settings.mock_mode is True
