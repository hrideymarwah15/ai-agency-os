"""Structured proposal generator fields.

Revision ID: 0009
Revises: 0008
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add structured proposal sections and lifecycle metadata."""
    # Existing deployments already own proposalstatus. Add values before the
    # table columns so ORM writes cannot fail after this revision applies.
    op.execute("ALTER TYPE proposalstatus ADD VALUE IF NOT EXISTS 'APPROVED'")
    op.execute("ALTER TYPE proposalstatus ADD VALUE IF NOT EXISTS 'DELIVERY_QUEUED'")
    columns = [
        ("executive_summary", sa.Text()),
        ("website_audit", postgresql.JSONB(), sa.text("'{}'::jsonb")),
        ("opportunity_analysis", postgresql.JSONB(), sa.text("'[]'::jsonb")),
        ("scope_of_work", postgresql.JSONB(), sa.text("'{}'::jsonb")),
        ("timeline", postgresql.JSONB(), sa.text("'{}'::jsonb")),
        ("pricing", postgresql.JSONB(), sa.text("'{}'::jsonb")),
        ("faqs", postgresql.JSONB(), sa.text("'[]'::jsonb")),
        ("testimonials", postgresql.JSONB(), sa.text("'[]'::jsonb")),
        ("terms", postgresql.JSONB(), sa.text("'{}'::jsonb")),
        ("next_steps", postgresql.JSONB(), sa.text("'{}'::jsonb")),
        ("negotiation_rounds", postgresql.JSONB(), sa.text("'[]'::jsonb")),
        ("final_price", sa.Numeric(12, 2)),
        ("owner_approved_at", sa.DateTime(timezone=True)),
        ("owner_approved_by", sa.String(255)),
        ("viewed_at", sa.DateTime(timezone=True)),
        ("generated_by", sa.String(100), sa.text("'proposal-generator'")),
        ("generation_time_ms", sa.Integer()),
        ("full_html", sa.Text()),
        ("section_html", postgresql.JSONB(), sa.text("'{}'::jsonb")),
        ("meeting_notes", sa.Text()),
        ("version", sa.Integer(), sa.text("1")),
        ("version_history", postgresql.JSONB(), sa.text("'[]'::jsonb")),
        ("client_access_token_hash", sa.String(128)),
        ("client_access_token_expires_at", sa.DateTime(timezone=True)),
    ]
    for item in columns:
        name, column_type, *default = item
        nullable = name not in {"generated_by", "version"}
        op.add_column(
            "proposals",
            sa.Column(name, column_type, nullable=nullable, server_default=default[0] if default else None),
        )
    op.create_index("ix_proposals_business_id", "proposals", ["business_id"])
    op.create_index("ix_proposals_status", "proposals", ["status"])
    op.create_index("ix_proposals_created_at", "proposals", ["created_at"])


def downgrade() -> None:
    """Remove structured proposal fields."""
    # PostgreSQL cannot remove enum labels in place. Rebuild the type after
    # normalizing rows that use the new lifecycle values.
    op.execute("UPDATE proposals SET status = 'DRAFT' WHERE status IN ('APPROVED', 'DELIVERY_QUEUED')")
    op.drop_index("ix_proposals_created_at", table_name="proposals")
    op.drop_index("ix_proposals_status", table_name="proposals")
    op.drop_index("ix_proposals_business_id", table_name="proposals")
    for name in [
        "client_access_token_expires_at", "client_access_token_hash", "version_history", "version",
        "meeting_notes", "section_html", "full_html", "generation_time_ms", "generated_by",
        "viewed_at", "owner_approved_by", "owner_approved_at", "final_price", "negotiation_rounds",
        "next_steps", "terms", "testimonials", "faqs", "pricing", "timeline", "scope_of_work",
        "opportunity_analysis", "website_audit", "executive_summary",
    ]:
        op.drop_column("proposals", name)
    op.execute("ALTER TABLE proposals ALTER COLUMN status TYPE text USING status::text")
    op.execute("DROP TYPE proposalstatus")
    op.execute("CREATE TYPE proposalstatus AS ENUM ('DRAFT', 'SENT', 'UNDER_NEGOTIATION', 'ACCEPTED', 'REJECTED', 'EXPIRED')")
    op.execute("ALTER TABLE proposals ALTER COLUMN status TYPE proposalstatus USING status::proposalstatus")
