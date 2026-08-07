# SPEC-001: Core System Architecture

## 1. Executive Summary

The AI Agency OS Core System Architecture defines the foundational infrastructure that orchestrates all specialized AI departments, manages inter-agent communication, handles human approval workflows, and ensures compliance, observability, and scalability. This specification covers the agent orchestration layer, message bus, state management, configuration system, and deployment architecture.

## 2. Problem Statement

Building an autonomous AI agency requires coordinating 15+ specialized AI agents (departments) that must:
- Share context and state securely
- Communicate asynchronously with guaranteed delivery
- Respect human approval gates for critical actions
- Maintain audit trails for every decision
- Scale horizontally as lead volume grows
- Operate 24/7 with minimal human intervention

Existing single-agent approaches fail because they lack departmental specialization, approval workflows, and auditability required for business operations.

## 3. User Personas

| Persona | Role | Needs |
|---------|------|-------|
| **Agency Owner** | Human operator | Define services/pricing/legal; approve contracts/payments; view dashboards |
| **CEO Agent** | AI orchestrator | Plan daily workflow; set revenue targets; coordinate departments |
| **Department Agents** | Specialized AI | Execute domain tasks; report progress; request approvals |
| **Client** | External | Receive proposals, contracts, deliverables, maintenance reports |
| **Auditor** | Compliance | Review AI decision logs; verify compliance |

## 4. User Journeys

### Journey 1: Daily Autonomous Cycle
```
Owner defines config → Scheduler triggers → CEO plans day → Departments execute → 
Results aggregated → Owner reviews approvals → Next cycle planned
```

### Journey 2: Human Approval Gate
```
Agent requests approval → Notification sent → Owner reviews context → 
Approve/Reject/Modify → Agent continues or escalates → Audit log recorded
```

### Journey 3: Error Recovery
```
Agent fails → Error captured → Retry with backoff → Escalate to CEO → 
CEO replans or requests human intervention → Recovery logged
```

## 5. Functional Requirements

### 5.1 Agent Orchestration
- **FR-001**: Support 15+ concurrent department agents with isolated contexts
- **FR-002**: Dynamic agent registration and discovery
- **FR-003**: Agent lifecycle management (start, pause, resume, terminate)
- **FR-004**: Resource quotas per agent (CPU, memory, API calls, tokens)

### 5.2 Message Bus
- **FR-005**: Pub/sub messaging with at-least-once delivery
- **FR-006**: Message persistence for replay and debugging
- **FR-007**: Priority queues for time-sensitive operations
- **FR-008**: Dead letter handling for failed messages

### 5.3 State Management
- **FR-009**: Distributed state store with ACID guarantees
- **FR-010**: Agent checkpointing for recovery
- **FR-011**: Cross-agent shared context with versioning
- **FR-012**: TTL-based cleanup for ephemeral state

### 5.4 Approval Workflow
- **FR-013**: Configurable approval gates per action type
- **FR-014**: Multi-channel notifications (Telegram, Email, Slack, Dashboard)
- **FR-015**: Approval timeout with escalation
- **FR-016**: Partial approval with modifications

### 5.5 Audit & Compliance
- **FR-017**: Immutable audit log for every AI decision
- **FR-018**: Structured logging with correlation IDs
- **FR-019**: PII redaction in logs
- **FR-020**: Export for compliance review

## 6. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Availability** | 99.9% uptime (8.76 hrs/year downtime) |
| **Latency (p99)** | <500ms for inter-agent messages |
| **Throughput** | 10,000 messages/second |
| **Scalability** | Horizontal to 100+ agents |
| **Recovery Time** | <30 seconds for agent restart |
| **Audit Retention** | 7 years immutable |
| **Security** | SOC 2 Type II ready |

## 7. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI AGENCY OS PLATFORM                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │   Owner     │  │  Auditor    │  │   Client    │  │  External  │ │
│  │  Dashboard  │  │  Portal     │  │  Portal     │  │   APIs     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
│         │                │                │                │        │
│         └────────────────┼────────────────┼────────────────┘        │
│                          ▼                ▼                         │
│                 ┌──────────────────────────────┐                   │
│                 │      API Gateway (FastAPI)   │                   │
│                 │  Auth │ Rate Limit │ Routing │                   │
│                 └──────────────┬───────────────┘                   │
│                                │                                   │
│         ┌──────────────────────┼──────────────────────┐            │
│         ▼                      ▼                      ▼            │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐     │
│  │  Message    │       │   State     │       │   Audit     │     │
│  │   Bus       │◄─────►│   Store     │◄─────►│   Log       │     │
│  │ (Redis/     │       │ (PostgreSQL │       │ (Append-    │     │
│  │  Kafka)     │       │  + pgvector)│       │  only DB)   │     │
│  └──────┬──────┘       └──────┬──────┘       └──────┬──────┘     │
│         │                     │                     │             │
│  ┌──────┴─────────────────────┴─────────────────────┴──────┐     │
│  │                    AGENT ORCHESTRATOR                     │     │
│  │  (LangGraph + Hermes)  │  Scheduler  │  Approval Engine  │     │
│  └──────┬─────────────────────┬─────────────────────┬──────┘     │
│         │                     │                     │             │
│  ┌──────┴──────┐      ┌──────┴──────┐      ┌──────┴──────┐      │
│  │  MARKET     │      │   SALES     │      │  DELIVERY   │      │
│  │  INTEL      │      │   DEPT      │      │  DEPT       │      │
│  │  • Scanner  │      │  • Outreach │      │  • PM       │      │
│  │  • Auditor  │      │  • Proposal │      │  • Design   │      │
│  │  • Lead     │      │  • Negotiate│      │  • Dev      │      │
│  │  • Score    │      │  • Contract │      │  • QA       │      │
│  └─────────────┘      └─────────────┘      │  • Deploy   │      │
│                                            │  • Support  │      │
│  ┌─────────────┐      ┌─────────────┐      └─────────────┘      │
│  │  FINANCE    │      │  LEGAL      │                             │
│  │  • Billing  │      │  • Contracts│                             │
│  │  • Payments │      │  • Compliance                           │
│  │  • MRR      │      │  • Templates                            │
│  └─────────────┘      └─────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
```

## 8. Data Models

### 8.1 Agent Registry
```python
class AgentRegistration(BaseModel):
    agent_id: str
    department: DepartmentType
    capabilities: List[str]
    config: AgentConfig
    status: AgentStatus
    resource_limits: ResourceQuota
    last_heartbeat: datetime
    metadata: Dict[str, Any]
```

### 8.2 Message Envelope
```python
class MessageEnvelope(BaseModel):
    message_id: UUID
    correlation_id: UUID
    causation_id: Optional[UUID]
    sender: str
    recipient: Union[str, List[str]]  # Direct or broadcast
    priority: MessagePriority
    payload: Dict[str, Any]
    headers: MessageHeaders
    timestamp: datetime
    ttl: Optional[int]
    retry_count: int
```

### 8.3 Approval Request
```python
class ApprovalRequest(BaseModel):
    request_id: UUID
    agent_id: str
    action_type: ApprovalActionType
    context: Dict[str, Any]
    proposed_action: Dict[str, Any]
    risk_level: RiskLevel
    expires_at: datetime
    status: ApprovalStatus
    human_response: Optional[ApprovalResponse]
    audit_trail: List[AuditEntry]
```

### 8.4 Audit Entry
```python
class AuditEntry(BaseModel):
    entry_id: UUID
    timestamp: datetime
    agent_id: str
    action: str
    decision: str
    rationale: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    confidence: float
    human_reviewed: bool
    correlation_id: UUID
```

## 9. API Contracts

### 9.1 Agent Registration
```
POST   /api/v1/agents/register
GET    /api/v1/agents/{agent_id}
PUT    /api/v1/agents/{agent_id}/status
DELETE /api/v1/agents/{agent_id}
GET    /api/v1/agents?department={dept}&status={status}
```

### 9.2 Message Bus
```
POST   /api/v1/messages/publish
POST   /api/v1/messages/subscribe
GET    /api/v1/messages/{message_id}
GET    /api/v1/messages?correlation_id={id}
DELETE /api/v1/messages/{message_id}/dlq
```

### 9.3 Approval Workflow
```
POST   /api/v1/approvals/request
GET    /api/v1/approvals/{request_id}
POST   /api/v1/approvals/{request_id}/respond
GET    /api/v1/approvals?status=pending&assignee={owner}
```

### 9.4 Audit Log
```
GET    /api/v1/audit?agent_id={id}&from={date}&to={date}
GET    /api/v1/audit/{entry_id}
POST   /api/v1/audit/export
```

## 10. UI/UX Specifications

### 10.1 Owner Dashboard
- **Real-time agent status grid** with health indicators
- **Approval queue** with priority, risk, context preview
- **Revenue pipeline** funnel visualization
- **Audit log explorer** with filters and search
- **Configuration panel** for services, pricing, legal templates

### 10.2 Agent Monitoring
- **Live message flow** visualization
- **Resource utilization** per agent
- **Error rate and latency** charts
- **Decision trace** for any business outcome

## 11. Component Library

### 11.1 Core Components
- `AgentCard` - Status, capabilities, metrics
- `ApprovalCard` - Context, risk, actions, timer
- `MetricCard` - KPI with trend
- `MessageFlowDiagram` - Real-time DAG visualization
- `AuditTimeline` - Expandable audit entries

### 11.2 Design Tokens
```css
:root {
  --color-charcoal: #1a1612;
  --color-ivory: #faf8f5;
  --color-gold: #c6a96c;
  --color-gold-light: #e8d5a8;
  --color-success: #2e7d32;
  --color-warning: #f57c00;
  --color-error: #c62828;
  --font-heading: 'Playfair Display', serif;
  --font-accent: 'Great Vibes', cursive;
  --font-body: 'DM Sans', sans-serif;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 16px;
  --shadow-soft: 0 2px 8px rgba(26,22,18,0.08);
  --shadow-medium: 0 8px 24px rgba(26,22,18,0.12);
}
```

## 12. Motion & Animation

| Interaction | Animation | Duration | Easing |
|-------------|-----------|----------|--------|
| Agent status change | Pulse + color transition | 300ms | ease-out |
| Approval request appears | Slide up + fade in | 400ms | ease-out-cubic |
| Message flow edge | Dash animation | 1000ms | linear (loop) |
| Metric value update | Count-up + highlight | 600ms | ease-out |
| Modal open | Scale + fade | 250ms | ease-out-back |

## 13. Accessibility

- **WCAG 2.1 AA** compliance minimum
- **Keyboard navigation** for all dashboard actions
- **Screen reader** announcements for status changes
- **Color contrast** ≥ 4.5:1 for text, 3:1 for UI elements
- **Focus indicators** visible on all interactive elements
- **Reduced motion** respect (prefers-reduced-motion)
- **High contrast mode** support

## 14. Performance Budgets

| Metric | Budget |
|--------|--------|
| Dashboard initial load | <2s (3G) |
| API p99 latency | <500ms |
| Message bus throughput | >10k msg/s |
| Agent startup time | <5s |
| Database query p95 | <100ms |
| WebSocket reconnection | <3s |
| Bundle size (dashboard) | <200KB gzipped |

## 15. Security Requirements

- **Authentication**: JWT with short expiry + refresh tokens
- **Authorization**: RBAC (Owner, Auditor, Agent, Client)
- **Encryption**: TLS 1.3 in transit, AES-256 at rest
- **Secrets**: HashiCorp Vault or AWS Secrets Manager
- **Rate limiting**: Per-agent, per-endpoint, adaptive
- **Audit**: All admin actions, approval decisions, config changes
- **Compliance**: GDPR, DPDP (India), CAN-SPAM ready

## 16. Testing Strategy

### 16.1 Unit Tests
- Agent registration/discovery
- Message serialization/deserialization
- Approval state machine
- Audit log integrity

### 16.2 Integration Tests
- Multi-agent workflow execution
- Approval timeout/escalation
- Message bus failure/recovery
- State store consistency

### 16.3 Chaos Engineering
- Agent kill/restart during workflow
- Network partition simulation
- Database failover
- Message bus overload

### 16.4 Contract Tests
- API schema validation
- Message format compatibility
- Approval workflow invariants

## 17. Deployment Strategy

### 17.1 Infrastructure
- **Kubernetes** (EKS/GKE) for orchestration
- **Helm charts** for each service
- **ArgoCD** for GitOps deployment
- **Istio** for service mesh

### 17.2 Environments
| Env | Purpose | Scale |
|-----|---------|-------|
| Dev | Development | 1 replica each |
| Staging | Integration testing | Production-like |
| Production | Live traffic | Auto-scaling 3-50 |

### 17.3 Release Process
1. Feature branch → PR → CI (tests, lint, security scan)
2. Merge to main → Staging deployment
3. Automated smoke tests in staging
4. Manual approval for production
5. Blue-green deployment to production
6. Health checks → Traffic switch
7. Post-deploy monitoring (30 min)

## 18. Monitoring & Observability

### 18.1 Metrics (Prometheus + Grafana)
- **Golden signals**: Latency, Traffic, Errors, Saturation
- **Business metrics**: Leads/day, Response rate, MRR, Deal velocity
- **Agent metrics**: Task completion rate, Token usage, Error rate

### 18.2 Logging (Loki + Grafana)
- Structured JSON logs
- Correlation ID propagation
- PII redaction pipeline
- Log retention: 30 days hot, 7 years cold

### 18.3 Tracing (Tempo/Jaeger)
- Distributed traces across agents
- Span attributes for business context
- Sampling: 100% for errors, 10% for success

### 18.4 Alerting
| Alert | Condition | Severity | Channel |
|-------|-----------|----------|---------|
| AgentDown | No heartbeat > 60s | Critical | PagerDuty + Telegram |
| ApprovalStuck | Pending > 4 hours | High | Telegram + Email |
| ErrorRate | >5% for 5 min | High | PagerDuty |
| QueueBacklog | >1000 messages | Medium | Telegram |
| CostSpike | API costs > 2x baseline | Medium | Email |

## 19. Rollback & Recovery

### 19.1 Rollback Procedures
- **Application**: ArgoCD rollout undo (≤2 min)
- **Database**: Point-in-time recovery (RPO < 5 min)
- **Message Bus**: Consumer group reset + replay
- **State**: Agent checkpoint restore

### 19.2 Disaster Recovery
- **RTO**: 30 minutes
- **RPO**: 5 minutes
- **Backup regions**: 2 (primary + standby)
- **Runbook**: Automated failover with manual confirmation

## 20. Open Questions & Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LLM API rate limits | High | High | Multi-provider fallback, local models (Ollama) |
| Anti-spam compliance | Medium | Critical | Strict opt-in, rate limits, unsubscribe links |
| Agent hallucination | Medium | High | Human approval gates, confidence thresholds |
| Data quality (leads) | High | Medium | Multi-source validation, confidence scoring |
| Cost overruns | Medium | High | Budget caps per agent, usage monitoring |
| Legal liability | Low | Critical | Insurance, clear ToS, human approval for contracts |
| Vendor lock-in | Low | Medium | Multi-cloud, open standards, portable data |