"""Pricing engine schema

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-10 00:00:00.000000

Adds pricing_runs and pricing_rule_versions tables for pricing engine audit trail.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    """Create pricing_runs and pricing_rule_versions tables."""
    # Create pricing_runs table
    op.create_table(
        "pricing_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("package_name", sa.String(length=100), nullable=False),
        sa.Column("service_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pricing_runs_pkey"),
    )
    op.create_index("ix_pricing_runs_correlation_id", "pricing_runs", ["correlation_id"], unique=False)
    op.create_index("ix_pricing_runs_package_name", "pricing_runs", ["package_name"], unique=False)
    op.create_index("ix_pricing_runs_created_at", "pricing_runs", ["created_at"], unique=False)
    
    # Create pricing_rule_versions table
    op.create_table(
        "pricing_rule_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("config_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pricing_rule_versions_pkey"),
    )
    op.create_index("ix_pricing_rule_versions_created_at", "pricing_rule_versions", ["created_at"], unique=False)
    op.create_index("ix_pricing_rule_versions_version", "pricing_rule_versions", ["version"], unique=False)


def downgrade() -> None:
    """Drop pricing_runs and pricing_rule_versions tables."""
    op.drop_index("ix_pricing_rule_versions_version", table_name="pricing_rule_versions")
    op.drop_index("ix_pricing_rule_versions_created_at", table_name="pricing_rule_versions")
    op.drop_table("pricing_rule_versions")
    
    op.drop_index("ix_pricing_runs_created_at", table_name="pricing_runs")
    op.drop_index("ix_pricing_runs_package_name", table_name="pricing_runs")
    op.drop_index("ix_pricing_runs_correlation_id", table_name="pricing_runs")
    op.drop_table("pricing_runs")