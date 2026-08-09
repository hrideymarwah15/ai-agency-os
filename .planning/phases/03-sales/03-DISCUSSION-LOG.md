# Phase 03: Sales — Discussion Log

**Date:** 2026-08-09  
**Mode:** default (interactive)  
**Areas discussed:** 5/5 (all selected via "all and just complete agency by end of this phase")

---

## Area 1: Outreach Channels & Providers

**Question:** Which channels first, provider choice, channel selection logic?

**Options presented:**
- Email (SendGrid) + LinkedIn (official API) — WhatsApp deferred
- Email only (simpler start)
- All three (Email, LinkedIn, WhatsApp) — full scope

**Decision:** Email (SendGrid) + LinkedIn (official API). WhatsApp deferred to v2.

**Rationale:** SendGrid already in config with dedicated IP/warmup. LinkedIn official API respects ToS. WhatsApp template approval overhead deferred. Channel selection: LinkedIn if decision-maker profile found via enrichment; else Email.

**Follow-up:** Anti-spam uses Phase 1 choke points (consent, suppression, unsubscribe). Sequences: 5-touch/14 days configurable via YAML. Reply classification: LLM with ≥0.8 confidence auto-handle, else escalate.

---

## Area 2: Pricing Engine & Config

**Question:** Config-driven vs code-driven? Where to store rules? Service-specific pricing? Dynamic adjustments?

**Options presented:**
- Config-driven (YAML, hot-reloadable) — like opportunities rules
- Code-driven (Python classes) — more control, less flexible
- Hybrid (YAML for params, Python for logic)

**Decision:** Config-driven (YAML) at `backend/config/pricing.yaml` — hot-reloadable.

**Rationale:** Matches opportunities rule engine pattern. Service packages from existing `service_catalog`. Input factors/weights per SPEC-003. Dynamic adjustments (bundles, long-term, referral) as config toggles. Output: recommended/min/target price, max discount, negotiation limits.

---

## Area 3: Negotiation Guardrails & LLM

**Question:** How to enforce hard constraints? LLM for responses vs templates? Escalation triggers?

**Options presented:**
- Strict code-enforced guardrails (LangGraph tool schemas + Pydantic) — LLM only for contextual responses
- LLM with prompt-based guardrails (risk of hallucination)
- Hybrid: code for min_price, LLM for rest

**Decision:** Strict code-enforced guardrails + LLM for contextual responses only.

**Rationale:** Hard constraints (min_price, no legal changes, no unsupported features, no timeline compression) must never be violated — code enforcement via LangGraph tool schemas with Pydantic validation. LLM generates objection handling, ROI walkthrough, value articulation — NOT pricing. Escalation triggers: >max_discount, legal changes, unsupported features, >5 rounds, deal >₹1L, non-standard payment terms. Strategy sequence locked per SPEC-003.

---

## Area 4: Proposal Templates & PDF

**Question:** Template system? PDF engine? Multi-format? Brand enforcement?

**Options presented:**
- Jinja2 + WeasyPrint (HTML→PDF, no Chrome, fast)
- Jinja2 + headless Chrome (Playwright) — full fidelity, heavier
- ReportLab (programmatic PDF) — no HTML/CSS reuse

**Decision:** Jinja2 component blocks + WeasyPrint for PDF. DOCX optional via python-docx.

**Rationale:** WeasyPrint uses HTML/CSS (reuses design tokens), no headless Chrome dependency, fast, good CSS support. Component blocks match SPEC-003 sections. Brand enforcement via CSS variable injection. Output: PDF (primary), HTML (web view), DOCX (optional).

---

## Area 5: Contract & Signature Flow

**Question:** Signature provider? Template system? Approval workflow? Payment schedule?

**Options presented:**
- DocuSign (primary, webhook support) + custom fallback
- HelloSign (simpler API)
- Custom only (PDF + manual upload)

**Decision:** DocuSign (industry standard, webhook support) with custom fallback.

**Rationale:** DocuSign has production webhook support for counter-signature tracking. Templates: Jinja2 with variable placeholders, service-specific clauses, jurisdiction variants. Approval: Owner approve → generate → send for signature → DocuSign webhook → executed storage. Payment: 50/50 or milestone from proposal pricing. Full audit trail via Phase 1 AuditService.

---

## Deferred Ideas Captured

1. WhatsApp Business API → v2 (template approval overhead)
2. LinkedIn connection automation → official API only, human-in-loop
3. Email verification provider → backlog
4. HubSpot/Pipedrive CRM sync → v2
5. Score calibration against close rates → SCOR-03 backlog
6. Churn prediction/health scoring → GROW-03
7. Seasonal pricing rules → post-v1
8. DocuSign alternatives → evaluate post-v1

---

## Summary

All 5 core sales pipeline areas decided. Implementation approach mirrors existing patterns from Phase 02.2 (rule engine, worker, YAML config), Phase 02.1 (audit runner/worker), Phase 1 (compliance, approval engine, audit log). Ready for planning.