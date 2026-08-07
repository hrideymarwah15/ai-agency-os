"""Opportunities and scoring schema

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-07 12:00:00.000000

Adds columns to businesses: opportunities JSONB, tier String, score_breakdown JSONB,
last_scored_at DateTime.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column(
            "opportunities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "businesses",
        sa.Column("tier", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column(
            "score_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "businesses",
        sa.Column(
            "last_scored_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Optional: add index on tier for filtering
    op.create_index("ix_businesses_tier", "businesses", ["tier"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_businesses_tier", table_name="businesses")
    op.drop_column("businesses", "last_scored_at")
    op.drop_column("businesses", "score_breakdown")
    op.drop_column("businesses", "tier")
    op.drop_column("businesses", "opportunities")
