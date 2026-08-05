"""Dedup tests — canonical keys + fuzzy merge (RESEARCH Pattern 3, deterministic).

Scenarios: same-domain merge with both lineage rows; exact phone merge; NO
false merge on shared names with divergent domain/phone; fuzzy secondary pass
with corroboration; idempotent lineage reuse on re-run of the same item.
"""

from uuid import uuid4

from sqlalchemy import select

from backend.database import (
    Business,
    BusinessSourceRecord,
    DiscoveryRun,
    RunStatus,
)
from backend.services.discovery.base import SourceCandidate
from backend.services.discovery.dedup import dedup_rate, ingest_candidate, names_match


async def _make_run(session) -> DiscoveryRun:
    """A real run row — business_source_records.run_id is FK'd to discovery_runs."""
    run = DiscoveryRun(
        trigger_source="TEST",
        status=RunStatus.RUNNING,
        correlation_id=f"corr-{uuid4().hex[:8]}",
    )
    session.add(run)
    await session.flush()
    return run


def _candidate(
    source_id: str, item_id: str, *, name: str, website=None, phone=None
) -> SourceCandidate:
    """Candidate with the unified normalized shape adapters produce."""
    normalized = {
        "name": name,
        "website": website,
        "phone": phone,
        "email": None,
        "location": None,
        "industry": None,
    }
    return SourceCandidate(
        source_id=source_id,
        source_item_id=item_id,
        raw={"mock": True},
        text=f"{name} {website or ''} {phone or ''}".strip(),
        normalized=normalized,
    )


async def _businesses(session) -> list[Business]:
    return (await session.execute(select(Business))).scalars().all()


async def _lineages(session) -> list[BusinessSourceRecord]:
    return (await session.execute(select(BusinessSourceRecord))).scalars().all()


async def test_same_domain_merges_with_both_lineages(migrated_db, discovery_db) -> None:
    """Two adapters, different names, same domain → one master, two lineage rows."""
    run = await _make_run(discovery_db)
    run_id = run.id
    master_a, status_a = await ingest_candidate(
        discovery_db,
        _candidate("mock_a", "a:1", name="Acme Tech Pvt. Ltd.", website="https://acme.example.com"),
        run_id=run_id,
    )
    master_b, status_b = await ingest_candidate(
        discovery_db,
        _candidate("mock_b", "b:1", name="Acme Tech", website="https://acme.example.com"),
        run_id=run_id,
    )
    await discovery_db.commit()

    assert status_a == "NEW"
    assert status_b == "MERGED"
    assert master_a.id == master_b.id
    businesses = await _businesses(discovery_db)
    assert len(businesses) == 1
    lineages = await _lineages(discovery_db)
    assert {row.source_id for row in lineages} == {"mock_a", "mock_b"}
    assert all(row.business_id == master_a.id for row in lineages)
    assert dedup_rate(1, 1) == 0.5


async def test_exact_phone_merges(migrated_db, discovery_db) -> None:
    """Same phone digits (different formatting) → merged, canonical phone key used."""
    run = await _make_run(discovery_db)
    run_id = run.id
    _, status_a = await ingest_candidate(
        discovery_db,
        _candidate(
            "mock_a",
            "a:1",
            name="Rapid Web Co",
            website="https://rapid.example.com",
            phone="+1 (415) 555-0132",
        ),
        run_id=run_id,
    )
    master_b, status_b = await ingest_candidate(
        discovery_db,
        _candidate(
            "mock_b",
            "b:1",
            name="Rapid Web Company",
            website="https://rapid2.example.com",
            phone="+1-415-555-0132",
        ),
        run_id=run_id,
    )
    await discovery_db.commit()

    assert status_a == "NEW"
    assert status_b == "MERGED"
    assert master_b.dedup_key_phone == "14155550132"


async def test_same_name_different_domains_phones_no_false_merge(migrated_db, discovery_db) -> None:
    """A shared name alone never merges (no corroboration) — two masters."""
    run = await _make_run(discovery_db)
    run_id = run.id
    master_a, status_a = await ingest_candidate(
        discovery_db,
        _candidate(
            "mock_a",
            "a:1",
            name="Acme Tech",
            website="https://acme.example.com",
            phone="1112223333",
        ),
        run_id=run_id,
    )
    master_b, status_b = await ingest_candidate(
        discovery_db,
        _candidate(
            "mock_b",
            "b:1",
            name="Acme Tech",
            website="https://acme2.example.com",
            phone="4445556666",
        ),
        run_id=run_id,
    )
    await discovery_db.commit()

    assert status_a == "NEW"
    assert status_b == "NEW"
    assert master_a.id != master_b.id
    assert len(await _businesses(discovery_db)) == 2
    assert dedup_rate(2, 0) == 0.0


async def test_fuzzy_merge_with_corroboration(migrated_db, discovery_db) -> None:
    """Near-identical names + corroborating phone → merged via the fuzzy pass."""
    run = await _make_run(discovery_db)
    run_id = run.id
    _, status_a = await ingest_candidate(
        discovery_db,
        _candidate(
            "mock_a",
            "a:1",
            name="Blue Whale Studio",
            website="https://blue.example.com",
            phone="1112223333",
        ),
        run_id=run_id,
    )
    _master_b, status_b = await ingest_candidate(
        discovery_db,
        _candidate(
            "mock_b",
            "b:1",
            name="Blue Whale Studios",
            website="https://blue2.example.com",
            phone="1112223333",
        ),
        run_id=run_id,
    )
    await discovery_db.commit()

    assert status_a == "NEW"
    assert status_b == "MERGED"
    assert len(await _businesses(discovery_db)) == 1
    assert names_match("blue whale studio", "blue whale studios")
    assert not names_match("acme tech", "acme web works")


async def test_below_threshold_name_no_merge(migrated_db, discovery_db) -> None:
    """Dissimilar names + no corroboration → never merged."""
    run = await _make_run(discovery_db)
    run_id = run.id
    master_a, status_a = await ingest_candidate(
        discovery_db,
        _candidate(
            "mock_a",
            "a:1",
            name="Acme Tech",
            website="https://acme.example.com",
            phone="1112223333",
        ),
        run_id=run_id,
    )
    master_b, status_b = await ingest_candidate(
        discovery_db,
        _candidate(
            "mock_b",
            "b:1",
            name="Acme Web Works",
            website="https://acme2.example.com",
            phone="4445556666",
        ),
        run_id=run_id,
    )
    await discovery_db.commit()

    assert status_a == "NEW"
    assert status_b == "NEW"
    assert master_a.id != master_b.id
    assert len(await _businesses(discovery_db)) == 2


async def test_rerun_reuses_lineage_row(migrated_db, discovery_db) -> None:
    """Re-running the same (source_id, source_item_id) never duplicates lineage."""
    run = await _make_run(discovery_db)
    run_id = run.id
    candidate = _candidate("mock_a", "a:1", name="Acme Tech", website="https://acme.example.com")
    master_a, status_first = await ingest_candidate(discovery_db, candidate, run_id=run_id)
    master_b, status_second = await ingest_candidate(discovery_db, candidate, run_id=run_id)
    await discovery_db.commit()

    assert status_first == "NEW"
    assert status_second == "REUSED"
    assert master_a.id == master_b.id
    assert len(await _businesses(discovery_db)) == 1
    assert len(await _lineages(discovery_db)) == 1


def test_dedup_rate_helpers() -> None:
    assert dedup_rate(0, 0) is None
    assert dedup_rate(2, 0) == 0.0
    assert dedup_rate(1, 1) == 0.5
