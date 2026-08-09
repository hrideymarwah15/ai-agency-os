# Phase 03: Sales - Context

**Gathered:** 2026-08-09
**Status:** Ready for planning
**Source:** SPEC-003, Phase 02/02.1/02.2 decisions, Phase 1 foundations

<domain>
## Phase Boundary

Complete the sales pipeline: from qualified leads (prioritized queue from Phase 02.2) through personalized outreach, proposal generation, pricing, negotiation, contract creation, and payment collection — all with human approval gates. The system automates 90% of sales work while keeping the owner in control of strategy, approvals, and relationship moments.

**Inputs from prior phases:**
- Phase 02.2: Prioritized lead queue with tier, score, top 3 opportunities, ROI estimates
- Phase 02.1: Website audit reports (scores, CWV, tech stack, gaps) for proposal integration
- Phase 02: Lead data (name, industry, website, contact, enrichment, source lineage)
- Phase 1: Audit log, compliance middleware, budget caps, scheduler, approval engine, auth

**Outputs to Phase 4:**
- Signed contracts with payment schedules
- Executed contract storage with audit trail
- Project creation triggers
</domain>

<decisions>
## Implementation Decisions

### 1. Outreach Channels & Providers
- **Channels (v1):** Email (SendGrid) + LinkedIn (official API). WhatsApp deferred to v2.
- **Provider:** SendGrid (dedicated IP, warmup, SPF/DKIM/DMARC) — already in config.
- **Channel selection logic:** LinkedIn if decision-maker profile found via enrichment; else Email.
- **Anti-spam compliance:** Consent records + suppression list + one-click unsubscribe (Phase 1 CMP-03/CMP-04).
- **Sequences:** 5-touch over 14 days, configurable via YAML (`backend/config/outreach.yaml`).
- **Reply classification:** LLM-based with confidence threshold (≥0.8 auto-handle, <0.8 escalate to owner).
- **Meeting scheduling:** Cal.com integration (configurable) — FR-017.

### 2. Pricing Engine & Config
- **Configuration:** Config-driven (YAML) at `backend/config/pricing.yaml` — hot-reloadable like opportunities rules.
- **Service packages:** Reuse existing `service_catalog` from `backend/config.py` (Websites: Starter/Business/Premium; Automations: Basic/Medium/Advanced; Chatbots; Custom AI).
- **Input factors & weights:** Hours (25%), Complexity (20%), Market Rate (15%), Competition (10%), Industry (10%), Size (10%), Expected ROI (5%), Historical Close Rate (5%).
- **Output model:** `recommended_price`, `minimum_price`, `target_price`, `max_discount_pct`, `profit_margin_pct`, `negotiation_limits` (bundle, timeline extension, maintenance, approval threshold).
- **Dynamic adjustments (config toggles):** Volume bundles (10-15%), long-term contracts (6/12mo), referral partner discounts, seasonal promos.

### 3. Negotiation Guardrails & LLM
- **Hard constraints (code-enforced via LangGraph tool schemas + Pydantic):**
  - Never below `minimum_price`
  - Never modify legal clauses (payment terms, IP, liability, termination)
  - Never promise unsupported features
  - Never compress timeline below minimum viable
- **LLM role:** Contextual response generation (objection handling, value articulation, ROI walkthrough) — NOT pricing decisions.
- **Guardrail enforcement:** LangGraph `negotiate` tool validates offer ≥ min_price, no legal changes, concessions within limits, round count.
- **Escalation triggers:** >max_discount_pct, legal change requests, unsupported features, >5 rounds no progress, deal value >₹1,00,000, payment terms outside standard.
- **Strategy sequence:** Anchor High → Highlight ROI → Offer Bundles (10-15%) → Offer Maintenance (3mo free) → Final Discount (up to max) → Close.

### 4. Proposal Templates & PDF
- **Template system:** Jinja2 component blocks (`executive_summary`, `audit_report`, `opportunity_analysis`, `scope`, `timeline`, `pricing`, `faqs`, `testimonials`, `terms`, `next_steps`) — each a `.j2` partial in `backend/templates/proposals/`.
- **Variable injection:** Lead data, research, audit report, pricing output, opportunities — all from structured Pydantic models.
- **PDF engine:** WeasyPrint (HTML→PDF, no headless Chrome, good CSS support, fast). Headless Chrome fallback only if WeasyPrint fails.
- **Output formats:** PDF (primary), HTML (web view), DOCX (optional via `python-docx` for owner edits).
- **Brand enforcement:** CSS variables from Phase 1 design tokens injected into template context.

### 5. Contract & Signature Flow
- **Document types:** Proposal (marketing), SOW, MSA, NDA, Invoice — lawyer-approved templates with variable placeholders.
- **Template system:** Jinja2 with service-specific clauses + jurisdiction variants (India/International) + version control with change log.
- **Approval workflow:** Owner approval required → `POST /contracts/generate` → `POST /contracts/{id}/send-for-signature` → DocuSign webhook → counter-signature tracking → executed storage.
- **Signature provider:** DocuSign (primary, webhook support) with custom fallback (PDF + manual signature upload).
- **Payment schedule:** 50/50 or milestone-based from proposal pricing.
- **Audit trail:** Every action logged with correlation_id (Phase 1 `AuditService`).

### Cross-Cutting
- **Compliance:** All outreach consults suppression list, consent records, unsubscribe (Phase 1 choke points). WhatsApp template approval + opt-in deferred to v2.
- **CRM sync:** Custom internal CRM (Phase 3 scope); HubSpot/Pipedrive connectors deferred to v2.
- **Multi-format proposals:** PDF/HTML/DOCX via template system.
- **Testing:** Unit tests for pricing calculations, guardrail enforcement, template rendering; integration tests for outreach sequence (mock channels), proposal generation, negotiation simulation.
- **Monitoring:** Metrics per SPEC-003 §18.1 (outreach sent, response rate, meetings booked, proposals generated, negotiation rounds, deal value, cycle time).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Specs
- `.planning/specs/sales/SPEC-003-sales-proposal-system.md` — Full sales/proposal spec (all FR-XXX)
- `.planning/specs/core/SPEC-001-core-system-architecture.md` — System architecture
- `.planning/specs/discovery/SPEC-002-lead-discovery-engine.md` — Lead model, audit integration

### Prior phases (built and committed)
- `.planning/phases/02.2-opportunities-and-scoring/02.2-CONTEXT.md` — OPP/SCOR decisions, lead queue
- `.planning/phases/02.1-website-audits/02.1-CONTEXT.md` — Audit results structure for proposal integration
- `.planning/phases/02-discovery/02-CONTEXT.md` — Lead model, compliant client, sanitization
- `.planning/phases/01-foundation-orchestration-core/1-CONTEXT.md` — D-01..D-20 (audit log, approval engine, compliance, scheduler, auth)

### Code (read to match patterns)
- `backend/services/opportunities/` — rule engine, scorer, worker patterns to mirror
- `backend/services/audits/` — runner/worker/router patterns
- `backend/services/compliance/` — robots, rate limits, send gates, suppression
- `backend/services/audit.py` — AuditService write path
- `backend/api/approvals.py`, `backend/api/discovery.py` — router + Jinja2 patterns
- `backend/templates/discovery.html`, `backend/static/app.css` — design tokens
- `backend/config.py` — service_catalog, pricing multipliers, settings pattern
- `backend/main.py` — lifespan wiring (scheduler, workers)

### Research
- `.planning/research/SUMMARY.md` — consolidated verdicts
- `.planning/research/PITFALLS.md` — legal/technical risk evidence (CAN-SPAM, DPDP, webhook idempotency)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `services/opportunities/` — rule engine (YAML config, hot-reload), scorer, worker pattern → mirror for pricing rules, outreach sequences
- `services/audits/` — runner/worker/router → mirror for outreach campaign worker, proposal generator
- `services/compliance/` — robots, rate limits, send gates, suppression, consent → reuse for outreach
- `services/audit.py` — `AuditService` correlation_id threading → reuse for all sales actions
- `services/scheduler.py` — APScheduler heartbeat/enqueue pattern → reuse for outreach daily sends, follow-up triggers
- `config.py` — `service_catalog`, `size_multipliers`, `industry_multipliers` → extend for pricing inputs
- `templates/discovery.html`, `base.html`, `static/app.css` — design tokens, Jinja2 layout

### Integration Points
- **Lead queue:** Phase 02.2 `Business` with `priority_score`, `tier`, `opportunities`, `last_scored_at` → Sales Orchestrator pulls from here
- **Audit data:** Phase 02.1 `WebsiteAudit` with scores, CWV, tech stack, gaps → Proposal Writer pulls for audit report
- **Compliance middleware:** Phase 1 `build_compliant_client()` → all outreach fetches
- **Approval engine:** Phase 1 LangGraph `interrupt()`/`Command(resume=...)` → proposal approval, contract approval, below-floor negotiation escalation
- **Budget caps:** Phase 1 per-provider LLM spend, outreach volume caps → enforce at outreach send, proposal generation
- **Audit log:** Phase 1 `AuditService` → every sales action (outreach send, reply, proposal generate, negotiate, contract)

### Established Patterns
- Async-only runtime — all agents/DB async; LangGraph nodes must be async
- Env-driven config via pydantic-settings — new outreach/pricing/negotiation settings follow this
- Black 100 / ruff / mypy strict — all new code must satisfy (CI gates)
- Postgres outbox pattern — durable side-effect queues (outreach sends, proposal generation, contract signing)
</code_context>

<specifics>
## Specific Ideas

- **Sales Orchestrator as LangGraph:** Single StateGraph: `Research → Outreach → Follow-up → Qualify → Meeting → Proposal → Negotiation → Contract`. Each node is an async function; approval gates use `interrupt()`.
- **Outreach Campaign Worker:** Drains `outreach.send` outbox topic, executes sequence steps, logs metrics, handles replies via webhook.
- **Proposal Generator:** Stateless service — input: lead_id + meeting notes → output: Proposal model → owner review page → approve → send to client.
- **Negotiation Agent:** Thin LLM wrapper with strict tool schema (`negotiate(price, concessions, rationale)`) validated by Pydantic; guardrails in tool, not prompt.
- **Owner Dashboard Extensions:** Sales pipeline kanban (New→Contacted→Replied→Qualified→Meeting→Proposal→Negotiation→Closed), proposal builder (editor+preview), negotiation thread.
- **Sequence Config:** YAML per sequence type (cold, warm, referral) with steps, templates, delays, branching on reply classification.
</specifics>

<deferred>
## Deferred Ideas

- WhatsApp Business API (template approval + opt-in management) → v2
- LinkedIn connection request automation (ToS risk) → official API only, human-in-loop for connections
- Email contact verification provider (bounce-risk) → LEAD-06/07 backlog
- HubSpot/Pipedrive CRM sync connectors → v2
- AI chatbot/dashboard delivery products → PROJ-05
- n8n-based automation delivery → PROJ-06
- Score calibration against close rates → SCOR-03
- Churn prediction/health scoring → GROW-03
- Seasonal/promotional pricing rules → after v1 stabilization
- DocuSign alternative (HelloSign/custom) → evaluate post-v1
</deferred>

---
Phase: 03-sales
Context gathered: 2026-08-09 via discuss-phase (all 5 areas)