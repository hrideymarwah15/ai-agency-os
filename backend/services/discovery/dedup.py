"""Dedup — canonical keys + Python fuzzy merge (RESEARCH Pattern 3, deterministic).

Per candidate: exact lookup on indexed canonical keys (domain/email/phone),
then a fuzzy secondary pass (name ratio >= FUZZY_THRESHOLD AND corroborating
domain/phone). New candidates become master records; hits attach a
BusinessSourceRecord lineage row and merge fill-if-missing fields (FR-062).
Dedup rate = merged / (new + merged) (D-25).
"""

from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import Business, BusinessSourceRecord
from backend.services.discovery.base import SourceCandidate
from backend.services.discovery.normalize import (
    normalize_domain,
    normalize_email,
    normalize_name,
    normalize_phone,
)

FUZZY_THRESHOLD = 0.85  # difflib ratio for the fuzzy name pass (A7)

_MASTER_FIELDS = (
    "name",
    "industry",
    "website_url",
    "email",
    "phone",
    "location",
    "employee_count",
    "rating",
    "review_count",
    "tech_stack",
)
# candidate.normalized key for each master field ("website" -> "website_url")
_FIELD_SOURCE = {
    "name": "name",
    "industry": "industry",
    "website_url": "website",
    "email": "email",
    "phone": "phone",
    "location": "location",
    "employee_count": "employee_count",
    "rating": "rating",
    "review_count": "review_count",
    "tech_stack": "tech_stack",
}


def names_match(name_a: str | None, name_b: str | None) -> bool:
    """Fuzzy name equality: difflib ratio at or above FUZZY_THRESHOLD."""
    if not name_a or not name_b:
        return False
    return SequenceMatcher(None, name_a, name_b).ratio() >= FUZZY_THRESHOLD


def dedup_rate(new_count: int, merged_count: int) -> float | None:
    """merged / (new + merged); None when nothing was ingested (D-25)."""
    total = new_count + merged_count
    if total == 0:
        return None
    return merged_count / total


def _candidate_keys(candidate: SourceCandidate) -> dict[str, str | None]:
    """Canonical dedup keys derived from the candidate's normalized fields."""
    normalized = candidate.normalized
    return {
        "dedup_key_domain": normalize_domain(normalized.get("website")),
        "dedup_key_email": normalize_email(normalized.get("email")),
        "dedup_key_phone": normalize_phone(normalized.get("phone")),
        "dedup_key_name": normalize_name(normalized.get("name")),
    }


async def find_master(session: AsyncSession, candidate: SourceCandidate) -> Business | None:
    """Exact indexed-key lookup first; fuzzy name pass only with corroboration."""
    keys = _candidate_keys(candidate)
    for column, value in keys.items():
        if not value or column == "dedup_key_name":
            continue  # a name alone is never a merge key (no false merges)
        row = (
            (
                await session.execute(
                    select(Business).where(getattr(Business, column) == value).limit(1)
                )
            )
            .scalars()
            .first()
        )
        if row is not None:
            return row
    # Fuzzy secondary pass: name ratio >= threshold AND corroborating domain/phone.
    candidate_name = keys["dedup_key_name"]
    if candidate_name:
        candidates = (
            (await session.execute(select(Business).where(Business.dedup_key_name.is_not(None))))
            .scalars()
            .all()
        )
        for master in candidates:
            if not names_match(master.dedup_key_name, candidate_name):
                continue
            if keys["dedup_key_domain"] and master.dedup_key_domain == keys["dedup_key_domain"]:
                return master
            if keys["dedup_key_phone"] and master.dedup_key_phone == keys["dedup_key_phone"]:
                return master
    return None


async def _create_master(session: AsyncSession, candidate: SourceCandidate) -> Business:
    """Create a master record with canonical dedup keys set."""
    normalized = candidate.normalized
    keys = _candidate_keys(candidate)
    master = Business(
        name=normalized.get("name") or "Unknown",
        industry=normalized.get("industry"),
        website_url=normalized.get("website"),
        email=normalized.get("email"),
        phone=normalized.get("phone"),
        location=normalized.get("location"),
        employee_count=normalized.get("employee_count"),
        rating=normalized.get("rating"),
        review_count=normalized.get("review_count"),
        tech_stack=normalized.get("tech_stack") or [],
        source=candidate.source_id,
        dedup_key_name=keys["dedup_key_name"],
        dedup_key_domain=keys["dedup_key_domain"],
        dedup_key_email=keys["dedup_key_email"],
        dedup_key_phone=keys["dedup_key_phone"],
    )
    session.add(master)
    return master


async def merge_into_master(
    session: AsyncSession,
    master: Business,
    candidate: SourceCandidate,
    *,
    run_id: UUID,
) -> None:
    """Fill-if-missing merge (FR-062/D-26) + a MERGED lineage row."""
    for field in _MASTER_FIELDS:
        if getattr(master, field) in (None, [], {}):
            setattr(master, field, candidate.normalized.get(_FIELD_SOURCE[field]))
    master.raw_data = master.raw_data or {}  # keep existing; never overwrite lineage
    session.add(
        BusinessSourceRecord(
            business_id=master.id,
            run_id=run_id,
            source_id=candidate.source_id,
            source_item_id=candidate.source_item_id,
            raw_payload=candidate.raw,
            sanitized_text=candidate.text,
            status="MERGED",
        )
    )


async def _existing_lineage(
    session: AsyncSession, candidate: SourceCandidate
) -> BusinessSourceRecord | None:
    """Idempotency check: (source_id, source_item_id) UNIQUE reuse (D-24)."""
    return (
        (
            await session.execute(
                select(BusinessSourceRecord).where(
                    BusinessSourceRecord.source_id == candidate.source_id,
                    BusinessSourceRecord.source_item_id == candidate.source_item_id,
                )
            )
        )
        .scalars()
        .first()
    )


async def ingest_candidate(
    session: AsyncSession,
    candidate: SourceCandidate,
    *,
    run_id: UUID,
) -> tuple[Business, str]:
    """Dedup + persist one candidate; returns (master, status NEW|MERGED|REUSED)."""
    existing = await _existing_lineage(session, candidate)
    if existing is not None:
        master = await session.get(Business, existing.business_id)
        if master is None:
            raise RuntimeError(f"lineage {existing.id} points at a missing business")
        return master, "REUSED"
    master = await find_master(session, candidate)
    if master is None:
        master = await _create_master(session, candidate)
        await session.flush()
        session.add(
            BusinessSourceRecord(
                business_id=master.id,
                run_id=run_id,
                source_id=candidate.source_id,
                source_item_id=candidate.source_item_id,
                raw_payload=candidate.raw,
                sanitized_text=candidate.text,
                status="NEW",
            )
        )
        return master, "NEW"
    await merge_into_master(session, master, candidate, run_id=run_id)
    return master, "MERGED"
