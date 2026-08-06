"""Database connection and models for AI Agency OS."""

import enum
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from supabase import Client, create_client

from backend.config import settings


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    """Return the current UTC time as a tz-aware datetime."""
    return datetime.now(UTC)


# ============================================
# Enums
# ============================================
class BusinessStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    AUDITED = "AUDITED"
    CONTACTED = "CONTACTED"
    NEGOTIATING = "NEGOTIATING"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"
    ONBOARDED = "ONBOARDED"


class ProposalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    UNDER_NEGOTIATION = "UNDER_NEGOTIATION"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ContractStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT_FOR_SIGNATURE = "SENT_FOR_SIGNATURE"
    SIGNED = "SIGNED"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class ProjectStatus(str, enum.Enum):
    INITIALIZED = "INITIALIZED"
    IN_DESIGN = "IN_DESIGN"
    IN_DEVELOPMENT = "IN_DEVELOPMENT"
    IN_QA = "IN_QA"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    MAINTAINED = "MAINTAINED"
    COMPLETED = "COMPLETED"
    ON_HOLD = "ON_HOLD"


class ServiceType(str, enum.Enum):
    WEBSITE = "WEBSITE"
    AUTOMATION = "AUTOMATION"
    AI_CHATBOT = "AI_CHATBOT"
    INTERNAL_AI = "INTERNAL_AI"


class TaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"


# ============================================
# SQLAlchemy Models
# ============================================
class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    social_links: Mapped[dict] = mapped_column(JSON, default=dict)
    tech_stack: Mapped[list] = mapped_column(JSON, default=list)
    audit_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    priority_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[BusinessStatus] = mapped_column(
        SQLEnum(BusinessStatus), default=BusinessStatus.DISCOVERED
    )
    estimated_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    decision_maker: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pain_points: Mapped[list] = mapped_column(JSON, default=list)
    growth_signals: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)
    # Discovery enrichment (LEAD-02) + dedup canonical keys (D-25)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_enriched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enrichment_version: Mapped[int] = mapped_column(Integer, default=1)
    dedup_key_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedup_key_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedup_key_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedup_key_phone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        Index("ix_businesses_status", "status"),
        Index("ix_businesses_industry", "industry"),
        Index("ix_businesses_priority", "priority_score"),
        Index("ix_businesses_dedup_key_domain", "dedup_key_domain"),
        Index("ix_businesses_dedup_key_email", "dedup_key_email"),
        Index("ix_businesses_dedup_key_phone", "dedup_key_phone"),
    )


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE")
    )
    performance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seo_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accessibility_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_practices_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    missing_features: Mapped[list] = mapped_column(JSON, default=list)
    automation_opportunities: Mapped[list] = mapped_column(JSON, default=list)
    ai_opportunities: Mapped[list] = mapped_column(JSON, default=list)
    estimated_roi: Mapped[str | None] = mapped_column(Text, nullable=True)
    cms: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hosting_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    traffic_estimate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    domain_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ssl_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    core_web_vitals: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_crawler_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE")
    )
    package_name: Mapped[str] = mapped_column(String(100), nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(SQLEnum(ServiceType), nullable=False)
    proposed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_offered_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recurring_monthly_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))
    scope_summary: Mapped[str] = mapped_column(Text, nullable=False)
    detailed_scope: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[ProposalStatus] = mapped_column(
        SQLEnum(ProposalStatus), default=ProposalStatus.DRAFT
    )
    human_approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    negotiation_history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("proposals.id", ondelete="CASCADE")
    )
    business_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE")
    )
    sow_text: Mapped[str] = mapped_column(Text, nullable=False)
    legal_terms: Mapped[str] = mapped_column(Text, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_schedule: Mapped[list] = mapped_column(JSON, default=list)
    is_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signature_data: Mapped[dict] = mapped_column(JSON, default=dict)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus), default=PaymentStatus.PENDING
    )
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    contract_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE")
    )
    business_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(SQLEnum(ServiceType), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(ProjectStatus), default=ProjectStatus.INITIALIZED
    )
    deployment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    staging_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    repo_branch: Mapped[str] = mapped_column(String(100), default="main")
    tasks: Mapped[list] = mapped_column(JSON, default=list)
    current_phase: Mapped[str | None] = mapped_column(String(100), nullable=True)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0)
    mrr_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # DESIGN, FRONTEND, BACKEND, TESTING, DEVOPS
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.TODO)
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Agent name
    priority: Mapped[int] = mapped_column(Integer, default=0)
    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    deliverables: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MaintenanceCheck(Base):
    __tablename__ = "maintenance_checks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    check_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # SSL, PERFORMANCE, UPTIME, LINKS, SEO, SECURITY, DEPENDENCIES
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # PASSED, WARNING, FAILED, AUTO_FIXED
    score: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    previous_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    issues_found: Mapped[list] = mapped_column(JSON, default=list)
    auto_fixed: Mapped[list] = mapped_column(JSON, default=list)
    report_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    report_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    client_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    duration_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))


class OutreachLog(Base):
    __tablename__ = "outreach_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE")
    )
    proposal_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("proposals.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # EMAIL, WHATSAPP, LINKEDIN
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # OUTBOUND, INBOUND
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="SENT"
    )  # SENT, DELIVERED, OPENED, REPLIED, BOUNCED
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (Index("ix_audit_logs_correlation_id", "correlation_id"),)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint("thread_id", name="uq_approval_requests_thread_id"),
        Index("ix_approval_requests_status", "status"),
    )


class LLMSpend(Base):
    __tablename__ = "llm_spend"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    spend_date: Mapped[date] = mapped_column(Date, nullable=False)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "provider", "model", "spend_date", name="uq_llm_spend_provider_model_date"
        ),
    )


class OutreachSpend(Base):
    __tablename__ = "outreach_spend"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    spend_date: Mapped[date] = mapped_column(Date, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint("spend_date", "channel", name="uq_outreach_spend_date_channel"),
    )


class SchedulerHeartbeat(Base):
    __tablename__ = "scheduler_heartbeats"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    last_beat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    lawful_basis: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SuppressionEntry(Base):
    __tablename__ = "suppression_entries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OutboxEvent(Base):
    """Durable side-effect job queue — ARCHITECTURE.md outbox_events table."""

    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING"
    )  # PENDING, IN_PROGRESS, DONE, FAILED, DEAD
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_outbox_events_status_next_run_at", "status", "next_run_at"),)


# ============================================
# Discovery Pipeline Models (D-28, D-24)
# ============================================
class RunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class SourceRunStatus(str, enum.Enum):
    OK = "OK"
    EMPTY = "EMPTY"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"
    EXCLUDED = "EXCLUDED"
    DISABLED = "DISABLED"


class DiscoveryRun(Base):
    """One discovery collection run (manual or scheduled trigger, D-28)."""

    __tablename__ = "discovery_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    trigger_source: Mapped[str] = mapped_column(String(20), nullable=False)  # MANUAL, SCHEDULER
    status: Mapped[RunStatus] = mapped_column(SQLEnum(RunStatus), default=RunStatus.RUNNING)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_candidates: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_discovery_runs_started_at", "started_at"),
        Index("ix_discovery_runs_correlation_id", "correlation_id"),
    )


class DiscoveryRunSourceStat(Base):
    """Per-source parse-success metrics for one run (LEAD-05; same-tx invariant)."""

    __tablename__ = "discovery_run_source_stats"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("discovery_runs.id", ondelete="CASCADE")
    )
    source_id: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[SourceRunStatus] = mapped_column(
        SQLEnum(SourceRunStatus), default=SourceRunStatus.OK
    )
    requests_made: Mapped[int] = mapped_column(Integer, default=0)
    found: Mapped[int] = mapped_column(Integer, default=0)
    parsed_ok: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    merged_count: Mapped[int] = mapped_column(Integer, default=0)
    rejection_buckets: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint("run_id", "source_id", name="uq_discovery_run_source_stat_run_source"),
    )


class BusinessSourceRecord(Base):
    """Lineage row: one candidate occurrence per (source, source_item_id) — D-24.

    The (source_id, source_item_id) UNIQUE is the idempotency key: a re-run of
    the same source item reuses the existing row, never duplicating lineage.
    raw_payload is the sanitized, size-capped source payload — never raw HTML
    (CMP-06).
    """

    __tablename__ = "business_source_records"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE")
    )
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("discovery_runs.id"))
    source_id: Mapped[str] = mapped_column(String(50), nullable=False)
    source_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sanitized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # NEW, MERGED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "source_id", "source_item_id", name="uq_business_source_record_source_item"
        ),
    )


# ============================================
# Website Audit Models (D-35, AUDT-01..04)
# ============================================
class AuditStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WebsiteAudit(Base):
    """One website audit run per lead (D-35) — re-audit inserts a new row (D-39).

    Status-carrying result row created at enqueue in the same transaction as the
    audit.run outbox event (RESEARCH Pattern 2, A5). Scores come from
    deterministic rule tables (D-36); CWV values carry methodology labels (D-34);
    scraped strings are sanitized before storage (CMP-06/D-42).
    """

    __tablename__ = "website_audits"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE")
    )
    status: Mapped[AuditStatus] = mapped_column(SQLEnum(AuditStatus), default=AuditStatus.RUNNING)
    performance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accessibility_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seo_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mobile_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cwv: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    tech_stack: Mapped[list] = mapped_column(JSONB, default=list)
    cms: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    hosting: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    analytics: Mapped[list] = mapped_column(JSONB, default=list)
    broken_links: Mapped[list] = mapped_column(JSONB, default=list)
    gaps: Mapped[list] = mapped_column(JSONB, default=list)
    security_headers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    raw_stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    audit_version: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_website_audits_business_started_at", "business_id", "started_at"),
    )


# ============================================
# Database Engine & Session
# ============================================
engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None
supabase_client: Client | None = None


def build_database_url(url: str) -> URL:
    """Return an asyncpg URL for the given DSN, never double-adding the driver."""
    parsed = make_url(url)
    if parsed.drivername in ("postgresql", "postgres"):
        parsed = parsed.set(drivername="postgresql+asyncpg")
    return parsed


def postgres_dsn() -> str:
    """Return the plain postgresql:// DSN (no driver suffix) for the LangGraph checkpointer."""
    return str(build_database_url(settings.database_url)).replace("+asyncpg", "", 1)


async def init_db() -> None:
    """Initialize the async engine and session factory (schema via Alembic, not create_all)."""
    global engine, async_session_maker, supabase_client

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set — cannot initialize the database")

    engine = create_async_engine(
        build_database_url(settings.database_url),
        echo=False,
        pool_size=10,
        max_overflow=20,
    )
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Supabase Client
    if settings.supabase_url and settings.supabase_key:
        supabase_client = create_client(settings.supabase_url, settings.supabase_key)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session; raise RuntimeError if not initialized."""
    if async_session_maker is None:
        raise RuntimeError("Database not initialized")
    async with async_session_maker() as session:
        yield session


async def close_db() -> None:
    """Dispose the engine and reset the module-level globals."""
    global engine, async_session_maker
    if engine is not None:
        await engine.dispose()
    engine = None
    async_session_maker = None


def get_supabase() -> Client | None:
    """Return the Supabase client, if configured."""
    return supabase_client
