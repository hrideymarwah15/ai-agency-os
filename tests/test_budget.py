"""Atomic budget-cap tests — FND-06/D-11: guarded UPDATE counters, hard-block + audit, pruning."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.config import settings
from backend.database import AuditLog, LLMSpend, OutreachSpend
from backend.services.budget import BudgetExceededError, prune_spend_rows, reserve_llm, reserve_outreach


@pytest.fixture
async def budget_db(test_session):
    """Clean the spend/audit tables the budget service writes to."""
    await test_session.execute(delete(LLMSpend))
    await test_session.execute(delete(OutreachSpend))
    await test_session.execute(delete(AuditLog).where(AuditLog.action == "budget_blocked"))
    await test_session.commit()
    yield test_session


async def _llm_row(session, provider="openrouter", model="model-a"):
    """Fetch the single llm_spend row for provider/model, or None."""
    result = await session.execute(
        select(LLMSpend).where(LLMSpend.provider == provider, LLMSpend.model == model)
    )
    return result.scalar_one_or_none()


async def test_reserve_llm_within_cap_creates_row(budget_db):
    await reserve_llm(budget_db, provider="openrouter", model="model-a", cost_cents=100)

    row = await _llm_row(budget_db)
    assert row is not None
    assert row.cost_cents == 100
    assert row.calls == 1
    assert row.spend_date == date.today()


async def test_reserve_llm_repeated_reserves_accumulate(budget_db):
    await reserve_llm(budget_db, provider="openrouter", model="model-a", cost_cents=100)
    await reserve_llm(budget_db, provider="openrouter", model="model-a", cost_cents=50)

    row = await _llm_row(budget_db)
    assert row is not None
    assert row.cost_cents == 150
    assert row.calls == 2


async def test_reserve_llm_over_cap_hard_blocks_and_audits(budget_db, monkeypatch):
    monkeypatch.setattr(settings, "llm_daily_budget_usd_openrouter", Decimal("1.00"))  # 100 cents

    await reserve_llm(budget_db, provider="openrouter", model="model-a", cost_cents=100)
    with pytest.raises(BudgetExceededError):
        await reserve_llm(budget_db, provider="openrouter", model="model-a", cost_cents=1)

    # Counter never exceeded the cap.
    row = await _llm_row(budget_db)
    assert row is not None
    assert row.cost_cents == 100

    # Audit row written for the blocked attempt.
    result = await budget_db.execute(
        select(AuditLog).where(AuditLog.action == "budget_blocked")
    )
    audit = result.scalars().all()
    assert len(audit) == 1
    assert audit[0].actor == "system"
    assert audit[0].entity_type == "llm_spend"
    assert audit[0].entity_id == "openrouter"
    assert audit[0].payload["cost_cents"] == 1
    assert audit[0].payload["cap_cents"] == 100


async def test_reserve_llm_atomic_under_concurrency(test_engine, budget_db, monkeypatch):
    """10 concurrent reserves at 25c against a 100c cap: exactly 4 fit, zero overspend."""
    monkeypatch.setattr(settings, "llm_daily_budget_usd_openrouter", Decimal("1.00"))  # 100 cents

    maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def one_reserve() -> None:
        async with maker() as session:
            await reserve_llm(session, provider="openrouter", model="race-model", cost_cents=25)

    results = await asyncio.gather(*(one_reserve() for _ in range(10)), return_exceptions=True)
    succeeded = [r for r in results if r is None]
    blocked = [r for r in results if isinstance(r, BudgetExceededError)]

    assert len(succeeded) == 4
    assert len(blocked) == 6

    async with maker() as session:
        total_cost = (
            await session.execute(
                select(func.coalesce(func.sum(LLMSpend.cost_cents), 0)).where(
                    LLMSpend.model == "race-model"
                )
            )
        ).scalar_one()
        total_calls = (
            await session.execute(
                select(func.coalesce(func.sum(LLMSpend.calls), 0)).where(
                    LLMSpend.model == "race-model"
                )
            )
        ).scalar_one()
    assert total_cost == 100  # exactly at cap — zero overspend
    assert total_calls == 4


async def test_reserve_outreach_within_limit(budget_db):
    for _ in range(settings.daily_outreach_limit):
        await reserve_outreach(budget_db, channel="EMAIL")

    result = await budget_db.execute(
        select(OutreachSpend).where(OutreachSpend.channel == "EMAIL")
    )
    row = result.scalar_one()
    assert row.sent_count == settings.daily_outreach_limit


async def test_reserve_outreach_over_limit_hard_blocks_and_audits(budget_db):
    for _ in range(settings.daily_outreach_limit):
        await reserve_outreach(budget_db, channel="EMAIL")

    with pytest.raises(BudgetExceededError):
        await reserve_outreach(budget_db, channel="EMAIL")

    result = await budget_db.execute(
        select(OutreachSpend).where(OutreachSpend.channel == "EMAIL")
    )
    row = result.scalar_one()
    assert row.sent_count == settings.daily_outreach_limit

    audit_result = await budget_db.execute(
        select(AuditLog).where(
            AuditLog.action == "budget_blocked",
            AuditLog.entity_type == "outreach_spend",
        )
    )
    audits = audit_result.scalars().all()
    assert len(audits) == 1
    assert audits[0].entity_id == "EMAIL"
    assert audits[0].payload["cap"] == settings.daily_outreach_limit


async def test_prune_spend_rows_deletes_older_than_retention(budget_db):
    old_date = date.today() - timedelta(days=40)
    await budget_db.execute(
        delete(LLMSpend).where(LLMSpend.provider == "openrouter", LLMSpend.model == "prune-old")
    )
    budget_db.add(LLMSpend(provider="openrouter", model="prune-old", spend_date=old_date, cost_cents=10, calls=1))
    await budget_db.execute(
        delete(LLMSpend).where(LLMSpend.provider == "openrouter", LLMSpend.model == "prune-fresh")
    )
    budget_db.add(LLMSpend(provider="openrouter", model="prune-fresh", spend_date=date.today(), cost_cents=10, calls=1))
    await budget_db.commit()

    await prune_spend_rows(budget_db, retention_days=30)

    assert await _llm_row(budget_db, model="prune-old") is None
    assert await _llm_row(budget_db, model="prune-fresh") is not None
