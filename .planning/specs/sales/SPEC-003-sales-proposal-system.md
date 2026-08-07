# SPEC-003: Sales & Proposal System

## 1. Executive Summary

The Sales & Proposal System automates the entire sales pipeline from personalized outreach through proposal generation, negotiation, and contract creation. It consists of specialized agents for research, outreach, proposal writing, pricing, and negotiation, all operating within human-defined guardrails and approval gates.

## 2. Problem Statement

Traditional agency sales requires significant human time for:
- Researching each prospect's business and pain points
- Writing personalized outreach that doesn't feel automated
- Creating custom proposals with audits, scope, pricing, timelines
- Negotiating within margins while preserving relationship
- Managing follow-ups and CRM updates

This system automates 90% of sales work while keeping humans in control of strategy, approvals, and relationship moments.

## 3. User Personas

| Persona | Role | Needs |
|---------|------|-------|
| **Sales Agent** | AI Department | Execute outreach sequences; manage conversations; book meetings |
| **Proposal Writer Agent** | AI Department | Generate customized proposals from templates + research |
| **Negotiation Agent** | AI Department | Handle price discussions within guardrails; escalate appropriately |
| **Pricing Engine** | AI Service | Calculate optimal pricing based on multiple factors |
| **Owner** | Human | Approve proposals/contracts; view pipeline; override agents |
| **Client** | External | Receive proposals; negotiate; sign contracts; make payments |

## 4. User Journeys

### Journey 1: Outbound Sales Cycle
```
Qualified Lead → Sales Agent Research → Personalized Outreach (Email/LinkedIn/WhatsApp) → 
Follow-up Sequence → Response Handling → Meeting Booked → Proposal Request
```

### Journey 2: Proposal Generation
```
Meeting Notes + Lead Data → Proposal Writer → Website Audit Integration → 
Opportunity Analysis → Scope Definition → Pricing Engine → 
Proposal Document → Owner Review → Send to Client
```

### Journey 3: Negotiation & Close
```
Client Counter-Offer → Negotiation Agent Evaluates → Within Guardrails? → 
Yes: Counter with ROI/Bundle/Maintenance → No: Escalate to Owner → 
Agreement → Contract Generation → Payment Collection → Project Creation
```

## 5. Functional Requirements

### 5.1 Sales Agent

#### 5.1.1 Research & Preparation
- **FR-001**: Deep business research using lead intelligence + web search
- **FR-002**: Identify decision makers via LinkedIn, website, Apollo-style enrichment
- **FR-003**: Map business to relevant service packages with specific pain points
- **FR-004**: Generate "hook" - specific, personalized reason for outreach

#### 5.1.2 Outreach Channels
- **FR-005**: Email (via SendGrid, Mailgun, or Gmail API)
- **FR-006**: LinkedIn (connection request + message sequence)
- **FR-007**: WhatsApp Business API (template messages + session messages)
- **FR-008**: X/Twitter DM (when appropriate)
- **FR-009**: Channel selection based on prospect presence and preferences

#### 5.1.3 Outreach Sequences
- **FR-010**: Configurable multi-touch sequences (5-7 touches over 14-21 days)
- **FR-011**: A/B testing for subject lines, hooks, CTAs
- **FR-012**: Dynamic personalization tokens (name, company, pain point, competitor, compliment)
- **FR-013**: Spintax support for variation at scale
- **FR-014**: Anti-spam compliance (unsubscribe, physical address, opt-out handling)

#### 5.1.4 Conversation Management
- **FR-015**: Inbound reply classification (interested, not interested, later, referral, question)
- **FR-016**: Objection handling with predefined response library
- **FR-017**: Meeting scheduling integration (Calendly, Cal.com, Google Calendar)
- **FR-018**: CRM sync (HubSpot, Pipedrive, or custom) with activity logging
- **FR-019**: Lead status progression: New → Contacted → Replied → Qualified → Meeting → Proposal

#### 5.1.5 Follow-up Automation
- **FR-020**: Time-based follow-ups (3 days, 7 days, 14 days)
- **FR-021**: Trigger-based follow-ups (email open, link click, website visit)
- **FR-022**: "Breakup" email sequence for non-responders
- **FR-023**: Re-engagement campaigns for lost/cold leads (quarterly)

### 5.2 Proposal Writer Agent

#### 5.2.1 Proposal Structure (All Sections Required)
- **FR-024**: Executive Summary (1 page, tailored to decision maker)
- **FR-025**: Website Audit Report (visual, scored, prioritized)
- **FR-026**: Opportunity Analysis (automation + AI, with ROI projections)
- **FR-027**: Scope of Work (deliverables, milestones, acceptance criteria)
- **FR-028**: Timeline (Gantt-style with dependencies)
- **FR-029**: Pricing (package + line items + optional add-ons)
- **FR-030**: FAQ (dynamic based on service type, industry, objections)
- **FR-031**: Testimonials (matched by industry/size/service)
- **FR-032**: Terms & Conditions (from legal templates)
- **FR-033**: Next Steps (clear CTA, expiration date, contact info)

#### 5.2.2 Dynamic Generation
- **FR-034**: Template system with Jinja2/Handlebars + component blocks
- **FR-035**: Variable injection from lead data, research, pricing, audit
- **FR-036**: Conditional sections (e.g., maintenance only for recurring services)
- **FR-037**: Multi-format output: PDF (primary), HTML (web view), DOCX (editable)
- **FR-038**: Brand enforcement (fonts, colors, logo, tone of voice)

#### 5.2.3 Audit Integration
- **FR-039**: Pull latest website intelligence report
- **FR-040**: Generate visual scorecards (performance, accessibility, SEO, UX)
- **FR-041**: Prioritize issues by business impact
- **FR-042**: Include screenshots/annotations of key issues

#### 5.2.4 ROI Calculations
- **FR-043**: Time savings × hourly cost × frequency = monthly value
- **FR-044**: Revenue uplift estimates (conversion rate × traffic × AOV)
- **FR-045**: Cost avoidance (manual errors, security incidents, downtime)
- **FR-046**: Payback period and 12/24-month ROI projections

### 5.3 Pricing Engine

#### 5.3.1 Input Factors
| Factor | Source | Weight |
|--------|--------|--------|
| Estimated Hours | Scope analysis + historical data | 25% |
| Complexity | Technical assessment (1-5) | 20% |
| Market Rate | Industry benchmarks + competitor data | 15% |
| Competition | Known competitors in deal | 10% |
| Industry | Vertical pricing power | 10% |
| Business Size | Employee count, revenue | 10% |
| Expected ROI | Opportunity analysis output | 5% |
| Historical Close Rate | CRM data for similar deals | 5% |

#### 5.3.2 Output Pricing Model
```python
class PricingOutput(BaseModel):
    recommended_price: int      # Target price for proposal
    minimum_price: int          # Floor (never go below)
    target_price: int           # Ideal outcome
    maximum_discount_pct: int   # Max % off recommended
    profit_margin_pct: float    # Expected margin
    negotiation_limits: NegotiationLimits
    
class NegotiationLimits(BaseModel):
    can_discount: bool
    max_discount_pct: int
    can_bundle: bool
    bundle_discount_pct: int
    can_extend_timeline: bool
    max_timeline_extension_weeks: int
    can_add_maintenance: bool
    maintenance_discount_pct: int
    requires_approval_above: int  # Price threshold for owner approval
```

#### 5.3.3 Service-Specific Pricing
- **FR-047**: Website packages (Starter/Business/Premium/Enterprise) with scope matrices
- **FR-048**: Automation complexity tiers (Basic/Medium/Advanced) with hour estimates
- **FR-049**: AI chatbot setup + monthly maintenance tiers
- **FR-050**: Custom AI systems (time & materials with cap)
- **FR-051**: Recurring revenue optimization (maintenance, hosting, AI credits, analytics)

#### 5.3.4 Dynamic Adjustments
- **FR-052**: Volume discounts for multi-service deals
- **FR-053**: Long-term contract discounts (6mo, 12mo)
- **FR-054**: Referral partner discounts
- **FR-055**: Seasonal/promotional pricing rules

### 5.4 Negotiation Agent

#### 5.4.1 Guardrails (Hard Constraints)
- **FR-056**: Never go below minimum_price
- **FR-057**: Never promise features outside scope without approval
- **FR-058**: Never modify legal clauses (payment terms, IP, liability, termination)
- **FR-059**: Never commit to timelines shorter than minimum viable
- **FR-060**: Escalate any request outside guardrails to Owner

#### 5.4.2 Negotiation Strategy (Sequenced)
1. **Anchor High**: Present recommended_price with value justification
2. **Highlight ROI**: Walk through specific ROI calculations for their business
3. **Offer Bundles**: Combine services for 10-15% bundle discount
4. **Offer Maintenance**: Include 3 months free maintenance (recurring revenue hook)
5. **Final Discount**: Up to maximum_discount_pct with clear "this is final" framing
6. **Close**: Send contract with payment schedule

#### 5.4.3 Conversation Handling
- **FR-061**: Parse client messages for pricing signals, objections, urgency
- **FR-062**: Maintain negotiation state (round, current offer, concessions made)
- **FR-063**: Generate contextual responses (not templates)
- **FR-064**: Detect "walk away" signals and escalate
- **FR-065**: Log all negotiation turns for audit trail

#### 5.4.4 Escalation Triggers
- **FR-066**: Client requests > maximum_discount_pct
- **FR-067**: Client requests legal changes
- **FR-068**: Client requests unsupported features
- **FR-069**: Deal value > approval threshold (configurable, default ₹1,00,000)
- **FR-070**: Negotiation exceeds 5 rounds without progress
- **FR-071**: Client requests payment terms outside standard (50/50 or milestone)

### 5.5 Contract Generator

#### 5.5.1 Document Types
- **FR-072**: Proposal (marketing document, not legally binding)
- **FR-073**: Statement of Work (detailed scope, deliverables, acceptance)
- **FR-074**: Master Services Agreement (legal terms, from template)
- **FR-075**: NDA (optional, mutual or one-way)
- **FR-076**: Invoice (with payment schedule)
- **FR-077**: Payment Schedule (milestone-based or 50/50)

#### 5.5.2 Template System
- **FR-078**: Lawyer-approved templates with variable placeholders
- **FR-079**: Service-specific clauses (website, automation, AI, maintenance)
- **FR-080**: Jurisdiction-specific variants (India, International)
- **FR-081**: Version control for templates with change log

#### 5.5.3 Approval Workflow
- **FR-082**: Owner approval required before sending any contract
- **FR-083**: Digital signature integration (DocuSign, HelloSign, or custom)
- **FR-084**: Counter-signature tracking
- **FR-085**: Executed contract storage with audit trail

## 6. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Outreach Personalization** | >80% unique content per prospect |
| **Response Rate** | >15% (cold), >40% (warm) |
| **Proposal Generation Time** | <5 minutes |
| **Negotiation Round Time** | <30 minutes per round |
| **Contract Turnaround** | <2 hours from approval |
| **CRM Sync Latency** | <30 seconds |
| **Anti-Spam Compliance** | 100% (CAN-SPAM, GDPR, DPDP) |
| **Audit Completeness** | 100% of sales actions logged |

## 7. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SALES & PROPOSAL SYSTEM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                               │
│  │  LEAD QUEUE  │◄──── Qualified leads from Discovery           │
│  │  (Priority)  │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    SALES ORCHESTRATOR                       │   │
│  │  (LangGraph: Research → Outreach → Follow-up → Qualify)   │   │
│  └──────────────┬────────────────────────────────────────────┘   │
│                 │                                                 │
│      ┌──────────┼──────────┐                                     │
│      ▼          ▼          ▼                                     │
│ ┌────────┐ ┌────────┐ ┌────────┐                                 │
│ │ RESEARCH│ │ OUTREACH│ │ FOLLOW- │                                 │
│ │ AGENT  │ │ AGENT  │ │ UP AGENT│                                 │
│ └────┬───┘ └────┬───┘ └────┬───┘                                 │
│      │          │          │                                     │
│      └──────────┼──────────┘                                     │
│                 ▼                                                 │
│        ┌────────────────┐                                         │
│        │  CRM SYNC      │                                         │
│        │  (HubSpot/     │                                         │
│        │   Custom)      │                                         │
│        └───────┬────────┘                                         │
│                │                                                   │
│                ▼                                                   │
│        ┌────────────────┐                                         │
│        │ MEETING BOOKED │                                         │
│        └───────┬────────┘                                         │
│                │                                                   │
│                ▼                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    PROPOSAL PIPELINE                        │   │
│  │  Meeting Notes → Proposal Writer → Pricing Engine →       │   │
│  │  Owner Review → Client Delivery → Negotiation → Contract  │   │
│  └──────────────┬────────────────────────────────────────────┘   │
│                 │                                                 │
│      ┌──────────┼──────────┐                                     │
│      ▼          ▼          ▼                                     │
│ ┌────────┐ ┌────────┐ ┌────────┐                                 │
│ │PROPOSAL│ │ PRICING │ │NEGOTIATION│                                │
│ │ WRITER │ │ ENGINE  │ │ AGENT    │                                 │
│ └────┬───┘ └────┬───┘ └────┬───┘                                 │
│      │          │          │                                     │
│      └──────────┼──────────┘                                     │
│                 ▼                                                 │
│        ┌────────────────┐                                         │
│        │ CONTRACT GEN   │                                         │
│        │ + APPROVAL     │                                         │
│        └───────┬────────┘                                         │
│                │                                                   │
│                ▼                                                   │
│        ┌────────────────┐                                         │
│        │ PAYMENT &      │                                         │
│        │ PROJECT CREATE │                                         │
│        └────────────────┘                                         │
└─────────────────────────────────────────────────────────────────┘
```

## 8. Data Models

### 8.1 Outreach Campaign
```python
class OutreachCampaign(BaseModel):
    campaign_id: UUID
    lead_id: UUID
    channel: OutreachChannel  # EMAIL, LINKEDIN, WHATSAPP, TWITTER
    sequence_id: str
    current_step: int
    status: CampaignStatus  # ACTIVE, PAUSED, COMPLETED, BOUNCED, OPTED_OUT
    created_at: datetime
    next_action_at: datetime
    metrics: CampaignMetrics

class CampaignMetrics(BaseModel):
    sent: int
    delivered: int
    opened: int
    clicked: int
    replied: int
    bounced: int
    unsubscribed: int
    meetings_booked: int
```

### 8.2 Outreach Message
```python
class OutreachMessage(BaseModel):
    message_id: UUID
    campaign_id: UUID
    step_number: int
    channel: OutreachChannel
    template_id: str
    rendered_content: str
    personalization_data: Dict[str, Any]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]
    replied_at: Optional[datetime]
    reply_content: Optional[str]
    reply_classification: Optional[ReplyClassification]
```

### 8.3 Proposal
```python
class Proposal(BaseModel):
    proposal_id: UUID
    lead_id: UUID
    version: int
    status: ProposalStatus  # DRAFT, PENDING_REVIEW, APPROVED, SENT, VIEWED, NEGOTIATING, ACCEPTED, REJECTED, EXPIRED
    
    # Content Sections
    executive_summary: str
    website_audit: WebsiteAuditSummary
    opportunity_analysis: List[OpportunitySummary]
    scope_of_work: ScopeOfWork
    timeline: ProjectTimeline
    pricing: ProposalPricing
    faqs: List[FAQ]
    testimonials: List[Testimonial]
    terms: TermsAndConditions
    next_steps: NextSteps
    
    # Metadata
    generated_by: str  # agent_id
    generation_time_ms: int
    owner_approved_at: Optional[datetime]
    owner_approved_by: Optional[str]
    sent_at: Optional[datetime]
    viewed_at: Optional[datetime]
    expires_at: datetime
    
    # Negotiation
    negotiation_rounds: List[NegotiationRound]
    final_price: Optional[int]
```

### 8.4 Negotiation Round
```python
class NegotiationRound(BaseModel):
    round_number: int
    initiated_by: NegotiationParty  # CLIENT, AGENT
    client_message: str
    agent_analysis: NegotiationAnalysis
    agent_response: str
    offered_price: Optional[int]
    concessions: List[Concession]
    status: RoundStatus  # PENDING, RESPONDED, ESCALATED, CLOSED
    created_at: datetime
    resolved_at: Optional[datetime]
```

### 8.5 Contract
```python
class Contract(BaseModel):
    contract_id: UUID
    proposal_id: UUID
    contract_type: ContractType  # MSA, SOW, NDA, INVOICE
    version: int
    status: ContractStatus  # DRAFT, PENDING_APPROVAL, PENDING_SIGNATURE, EXECUTED, EXPIRED
    
    # Content
    template_id: str
    rendered_content: str
    variables: Dict[str, Any]
    
    # Parties
    agency_signatory: Signatory
    client_signatory: Signatory
    
    # Signatures
    agency_signed_at: Optional[datetime]
    agency_signature_id: Optional[str]
    client_signed_at: Optional[datetime]
    client_signature_id: Optional[str]
    
    # Payment
    payment_schedule: PaymentSchedule
    total_amount: int
    currency: str = "INR"
    
    # Metadata
    created_at: datetime
    executed_at: Optional[datetime]
    expires_at: Optional[datetime]
```

## 9. API Contracts

### 9.1 Outreach Management
```
POST   /api/v1/outreach/campaigns
GET    /api/v1/outreach/campaigns?lead_id={id}&status=active
GET    /api/v1/outreach/campaigns/{campaign_id}
POST   /api/v1/outreach/campaigns/{campaign_id}/pause
POST   /api/v1/outreach/campaigns/{campaign_id}/resume
POST   /api/v1/outreach/campaigns/{campaign_id}/skip-step
GET    /api/v1/outreach/messages?campaign_id={id}
POST   /api/v1/outreach/reply-webhook  # Inbound email/WhatsApp webhook
```

### 9.2 Proposal Management
```
POST   /api/v1/proposals/generate
GET    /api/v1/proposals/{proposal_id}
GET    /api/v1/proposals/{proposal_id}/pdf
GET    /api/v1/proposals/{proposal_id}/html
PUT    /api/v1/proposals/{proposal_id}  # Owner edits
POST   /api/v1/proposals/{proposal_id}/approve
POST   /api/v1/proposals/{proposal_id}/send
POST   /api/v1/proposals/{proposal_id}/negotiate
GET    /api/v1/proposals?status=negotiating
```

### 9.3 Pricing Engine
```
POST   /api/v1/pricing/calculate
POST   /api/v1/pricing/validate-negotiation
GET    /api/v1/pricing/rules
PUT    /api/v1/pricing/rules/{rule_id}
```

### 9.4 Negotiation
```
GET    /api/v1/negotiations/{proposal_id}
POST   /api/v1/negotiations/{proposal_id}/respond
POST   /api/v1/negotiations/{proposal_id}/escalate
GET    /api/v1/negotiations/{proposal_id}/history
```

### 9.5 Contracts
```
POST   /api/v1/contracts/generate
GET    /api/v1/contracts/{contract_id}
GET    /api/v1/contracts/{contract_id}/pdf
POST   /api/v1/contracts/{contract_id}/send-for-signature
POST   /api/v1/contracts/webhook  # DocuSign/HelloSign webhook
GET    /api/v1/templates
POST   /api/v1/templates
PUT    /api/v1/templates/{template_id}
```

## 10. UI/UX Specifications

### 10.1 Sales Pipeline Dashboard
- **Kanban board**: New → Contacted → Replied → Qualified → Meeting → Proposal → Negotiation → Closed Won/Lost
- **Lead cards**: Name, company, tier, last activity, next action, owner (AI/Human)
- **Activity feed**: Real-time log of emails sent, opens, replies, meetings booked
- **Performance metrics**: Response rate, meeting rate, proposal rate, close rate, cycle time

### 10.2 Proposal Builder (Owner Review)
- **Section navigator**: Collapsible sidebar with all proposal sections
- **Live preview**: Side-by-side editor/preview
- **Inline editing**: Click-to-edit any text block
- **Variable highlights**: Show which content is dynamic vs static
- **Pricing panel**: Editable line items with margin indicators
- **Approval button**: Prominent "Approve & Send" with confirmation modal

### 10.3 Negotiation View
- **Conversation thread**: Client messages, agent responses, internal notes
- **Pricing timeline**: Visual history of offers/counter-offers
- **Guardrail indicators**: Green/yellow/red for each constraint
- **Escalation button**: "Request Owner Input" with context summary
- **Quick actions**: Approve discount, add maintenance, extend timeline, escalate

## 11. Component Library

- `PipelineKanban` - Drag-drop columns, card preview, filters
- `LeadCard` - Avatar, name, company, tier badge, score, next action
- `ActivityTimeline` - Infinite scroll, filter by type, real-time updates
- `ProposalEditor` - Section tree, live preview, inline edit, version history
- `PricingTable` - Editable rows, margin calc, bundle toggles
- `NegotiationThread` - Message bubbles, price badges, concession tags
- `ContractViewer` - Clause navigation, redline view, signature status
- `MetricCards` - Response rate, meeting rate, avg deal size, cycle time

## 12. Motion & Animation

| Interaction | Animation | Duration |
|-------------|-----------|----------|
| Kanban card drag | Lift + opacity | 150ms |
| Column drop | Slide + settle | 200ms |
| Proposal section expand | Height animate + fade | 250ms |
| Price update | Count-up + highlight | 400ms |
| New message appear | Slide up + fade | 300ms |
| Guardrail status change | Pulse + color | 300ms |
| Modal open | Scale + fade + backdrop | 200ms |

## 13. Accessibility

- Full keyboard navigation for pipeline and proposal editor
- Screen reader labels for all status badges and metrics
- Color-blind safe status colors (not just red/green)
- Focus trapping in modals
- ARIA live regions for real-time updates
- High contrast mode support

## 14. Performance Budgets

| Operation | Budget |
|-----------|--------|
| Proposal generation | <5s |
| PDF render | <3s |
| Outreach send (batch 100) | <30s |
| Negotiation response gen | <10s |
| Contract generation | <2s |
| Dashboard load (500 leads) | <1.5s |
| CRM sync (per lead) | <5s |

## 15. Security Requirements

- **Outbound Email**: DKIM, SPF, DMARC configured
- **WhatsApp**: Business API with approved templates only
- **LinkedIn**: Respect rate limits, no automation ToS violation
- **Data**: Prospect PII encrypted, minimal retention
- **Contracts**: Signed documents immutable, tamper-evident
- **Audit**: All sales actions logged with agent ID, timestamp, rationale
- **Compliance**: Unsubscribe honored within 24h, data deletion on request

## 16. Testing Strategy

### 16.1 Unit Tests
- Outreach template rendering with spintax
- Reply classification accuracy (>90% on test set)
- Pricing engine calculations with fixtures
- Negotiation guardrail enforcement
- Contract variable substitution

### 16.2 Integration Tests
- End-to-end outreach sequence (mock channels)
- Proposal generation from lead data
- Negotiation simulation with test scenarios
- Contract generation + signature flow (mock provider)

### 16.3 Contract Tests
- API schemas for all endpoints
- Webhook payloads (email, WhatsApp, DocuSign)
- CRM sync payloads

### 16.4 Compliance Tests
- Unsubscribe flow
- Data deletion request
- Rate limit adherence per channel
- Template approval enforcement (WhatsApp)

## 17. Deployment Strategy

### 17.1 Services
- **Sales Orchestrator**: Stateful LangGraph deployment (1-3 replicas)
- **Outreach Workers**: Stateless, horizontal scaling (5-50 based on queue)
- **Proposal Generator**: CPU-intensive, GPU optional for PDF (2-10 replicas)
- **Negotiation Agent**: Low latency, keep warm (2-5 replicas)

### 17.2 Queue Management
- **Outreach Queue**: Priority by lead tier + time waiting
- **Proposal Queue**: FIFO with owner review priority lane
- **Negotiation Queue**: Real-time, WebSocket preferred

### 17.3 External Dependencies
- **Email**: SendGrid/Mailgun (dedicated IP, warmup)
- **WhatsApp**: Meta Business API (template approval required)
- **LinkedIn**: Official API or approved partner
- **Signatures**: DocuSign API (production account)

## 18. Monitoring & Observability

### 18.1 Metrics
- `outreach_sent_total` (counter by channel, template)
- `outreach_response_rate` (gauge by channel, sequence)
- `meetings_booked_total` (counter)
- `proposals_generated_total` (counter)
- `proposal_generation_duration_seconds` (histogram)
- `negotiation_rounds_per_deal` (histogram)
- `negotiation_duration_days` (histogram)
- `deals_closed_total` (counter by won/lost)
- `deal_value_inr` (histogram)
- `sales_cycle_days` (histogram)

### 18.2 Logs
- Every outreach send with template, personalization hash
- Every reply with classification confidence
- Every proposal version with diff
- Every negotiation turn with guardrail check results
- Every contract action with signatory info

### 18.3 Alerts
| Alert | Condition | Severity |
|-------|-----------|----------|
| OutreachBounceRate | >5% bounce in 1hr | Critical |
| ResponseRateDrop | <5% response rate for 24h | High |
| ProposalStuckInReview | >48h pending owner | High |
| NegotiationStalled | >5 rounds no progress | Medium |
| ContractUnsigned | >7 days sent, not signed | Medium |
| SpamComplaint | Any spam complaint | Critical |

## 19. Rollback & Recovery

- **Outreach failure**: Retry with exponential backoff (max 3), then dead letter
- **Proposal generation failure**: Fallback to template-only mode, alert owner
- **Negotiation agent error**: Escalate to owner immediately, preserve context
- **Contract signature failure**: Manual fallback process documented
- **CRM sync failure**: Queue for retry, alert after 3 failures

## 20. Open Questions & Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LinkedIn automation ban | High | High | Use official API only, human-in-loop for connection requests |
| WhatsApp template rejection | Medium | Medium | Pre-approve templates, fallback to email |
| Email deliverability issues | Medium | High | Dedicated IP, warmup, monitoring, authentication |
| Negotiation hallucination | Medium | High | Strict guardrails, confidence thresholds, escalation |
| Proposal quality variance | Medium | Medium | Template reviews, A/B testing, owner spot-checks |
| Legal liability (contracts) | Low | Critical | Lawyer-approved templates, owner approval mandatory |
| Client data privacy | Low | Critical | Minimal PII storage, encryption, deletion workflows |
| Competitive response | Medium | Low | Continuous template optimization, unique value props |