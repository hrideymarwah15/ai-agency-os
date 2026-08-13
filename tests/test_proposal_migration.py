"""Static migration semantics for proposal enum evolution."""

from pathlib import Path


def test_proposal_migration_adds_enum_values_before_columns() -> None:
    source = Path("backend/alembic/versions/0009_proposal_generator.py").read_text()
    approved = source.index("ALTER TYPE proposalstatus ADD VALUE IF NOT EXISTS 'APPROVED'")
    queued = source.index("ALTER TYPE proposalstatus ADD VALUE IF NOT EXISTS 'DELIVERY_QUEUED'")
    columns = source.index("columns = [")
    assert approved < columns
    assert queued < columns


def test_proposal_migration_downgrade_rebuilds_enum_realistically() -> None:
    source = Path("backend/alembic/versions/0009_proposal_generator.py").read_text()
    assert "UPDATE proposals SET status = 'DRAFT'" in source
    assert "ALTER TABLE proposals ALTER COLUMN status TYPE text USING status::text" in source
    assert "DROP TYPE proposalstatus" in source
    assert "CREATE TYPE proposalstatus AS ENUM ('DRAFT', 'SENT'" in source
    assert "USING status::proposalstatus" in source
