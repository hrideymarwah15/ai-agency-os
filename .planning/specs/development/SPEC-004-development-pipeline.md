# SPEC-004: Development Pipeline & Delivery System

## 1. Executive Summary

The Development Pipeline automates the end-to-end delivery of websites, automations, AI systems, and custom internal tools. It coordinates specialized AI departments (Project Manager, Designer, Developer, QA, DevOps) through a structured workflow from signed contract to deployed, monitored production system with ongoing maintenance.

## 2. Problem Statement

Agency delivery is typically manual, inconsistent, and doesn't scale. Challenges include:
- Translating scope into technical tasks consistently
- Coordinating design, development, QA across time zones
- Ensuring quality standards (accessibility, performance, security)
- Managing deployments across multiple platforms
- Providing ongoing maintenance without human overhead
- Tracking progress and communicating with clients

## 3. User Personas

| Persona | Role | Needs |
|---------|------|-------|
| **Project Manager Agent** | AI Department | Create tasks, timelines, dependencies; track progress; report status |
| **Designer Agent** | AI Department | Brand-compliant UI/UX; component library; design tokens; accessibility |
| **Developer Agent** | AI Department | Write code; implement features; integrate APIs; follow patterns |
| **QA Agent** | AI Department | Test plans; automated testing; accessibility audits; performance budgets |
| **DevOps Agent** | AI Department | Deploy; configure monitoring; manage infrastructure; CI/CD |
| **Support Agent** | AI Department | Maintenance checks; client communication; issue resolution |
| **Client** | External | Progress visibility; approval gates; deliverable review; support access |

## 4. User Journeys

### Journey 1: Project Initialization
```
Contract Signed → Project Created → Scope Parsed → WBS Generated → 
Tasks Created → Timeline Built → Team Assigned → Kickoff Notification
```

### Journey 2: Design Phase
```
PM Assigns Design Tasks → Designer Reviews Brand/Requirements → 
Design System Applied → Components Created → Pages Designed → 
Accessibility Review → Client Review → Approval → Handoff to Dev
```

### Journey 3: Development Phase
```
PM Assigns Dev Tasks → Developer Implements → Code Review (Automated) → 
Unit Tests Written → Integration Tests → PR Created → CI Passes → 
Merge → Staging Deploy → QA Triggered
```

### Journey 4: QA & Deployment
```
QA Runs Test Suite → Accessibility Audit → Performance Audit → 
Security Scan → Issues Triaged → Fixes Applied → Re-test → 
Production Deploy → Smoke Tests → Monitoring Active → Client Handoff
```

### Journey 5: Maintenance Cycle
```
Monthly Scheduler → Health Checks Run → Issues Detected → 
Auto-fix or Ticket Created → Client Report Generated → 
Upsell Opportunities Identified → Next Cycle Scheduled
```

## 5. Functional Requirements

### 5.1 Project Management Department

#### 5.1.1 Project Creation
- **FR-001**: Auto-create project from signed contract + proposal scope
- **FR-002**: Parse scope into Work Breakdown Structure (WBS)
- **FR-003**: Generate task hierarchy: Epic → Feature → Task → Subtask
- **FR-004**: Estimate effort per task using historical velocity data
- **FR-005**: Build project timeline with dependencies (Gantt)
- **FR-006**: Assign tasks to appropriate AI departments
- **FR-007**: Set up project workspace (repo, board, docs, environments)

#### 5.1.2 Progress Tracking
- **FR-008**: Real-time task status (Todo → In Progress → Review → Done)
- **FR-009**: Burndown charts, velocity tracking
- **FR-010**: Blocking issue detection and escalation
- **FR-011**: Client-facing progress dashboard (simplified)
- **FR-012**: Automated status reports (daily standup, weekly summary)
- **FR-013**: Milestone gates with approval requirements

#### 5.1.3 Communication
- **FR-014**: Structured updates to client (email/portal/WhatsApp)
- **FR-015**: Internal agent coordination via message bus
- **FR-016**: Decision log for architectural choices
- **FR-017**: Change request management (scope creep control)

### 5.2 Design Department

#### 5.2.1 Design System
- **FR-018**: Brand guideline enforcement (colors, typography, spacing, logo usage)
- **FR-019**: Design token system (Figma Tokens / Style Dictionary compatible)
- **FR-020**: Component library (React + Tailwind) with Storybook documentation
- **FR-021**: Pattern library for common layouts (hero, features, pricing, testimonials, forms)
- **FR-022**: Responsive breakpoints and fluid typography system

#### 5.2.2 Design Process
- **FR-023**: Generate design brief from project requirements + brand audit
- **FR-024**: Create wireframes for key pages (mobile-first)
- **FR-025**: Design high-fidelity mockups for approval
- **FR-026**: Accessibility-first design (WCAG 2.1 AA from start)
- **FR-027**: Design handoff with specs (spacing, colors, interactions, states)
- **FR-028**: Design QA checklist before dev handoff

#### 5.2.3 Client Collaboration
- **FR-029**: Interactive prototype for client review (Figma/Excalidraw)
- **FR-030**: Annotation and feedback collection
- **FR-031**: Version control for designs
- **FR-032**: Approval gates with formal sign-off

### 5.3 Development Department

#### 5.3.1 Technology Standards
- **FR-033**: Next.js 14 (App Router) + TypeScript strict mode
- **FR-034**: Tailwind CSS v4 with design tokens
- **FR-035**: Framer Motion for animations
- **FR-036**: ESLint + Prettier + Husky pre-commit
- **FR-037**: Component architecture: Atomic Design (atoms, molecules, organisms, templates, pages)

#### 5.3.2 Service-Specific Implementations

**Website Development:**
- **FR-038**: Landing Pages (single page, conversion-optimized)
- **FR-039**: Portfolio Websites (gallery, case studies, CMS)
- **FR-040**: Business Websites (multi-page, blog, team, services)
- **FR-041**: SaaS Websites (marketing + auth + dashboard shell)
- **FR-042**: E-commerce (Products, Cart, Checkout, Payments, Orders)
- **FR-043**: Dashboards (Charts, Tables, Real-time, Role-based)
- **FR-044**: Internal Portals (Auth, RBAC, Workflows, Reports)

**Automation Implementation:**
- **FR-045**: n8n workflow development (visual + code)
- **FR-046**: WhatsApp Business API integration
- **FR-047**: CRM automation (HubSpot, Pipedrive, custom)
- **FR-048**: Email automation (sequences, triggers, templates)
- **FR-049**: Google Workspace automation (Sheets, Docs, Calendar, Gmail)
- **FR-050**: AI Customer Support (ticket routing, auto-response, escalation)

**AI Systems:**
- **FR-051**: Chatbot development (LangGraph + RAG)
- **FR-052**: Customer Support Bot (knowledge base + escalation)
- **FR-053**: Sales Bot (qualification, booking, handoff)
- **FR-054**: Reception Bot (scheduling, FAQ, routing)
- **FR-055**: Booking Bot (availability, confirmation, reminders)
- **FR-056**: Internal Knowledge Assistant (RAG + citations)
- **FR-057**: Custom AI CRM/ERP (entities, workflows, reporting)

#### 5.3.3 Development Practices
- **FR-058**: Feature branches with conventional commits
- **FR-059**: Automated code review (security, performance, style)
- **FR-060**: Unit tests (Jest + React Testing Library) - target 80% coverage
- **FR-061**: Integration tests (API routes, database, external services)
- **FR-062**: E2E tests (Playwright) for critical user flows
- **FR-063**: Type-safe API contracts (tRPC or OpenAPI + Orval)
- **FR-064**: Database migrations (Prisma/Drizzle) with review

### 5.4 QA Department

#### 5.4.1 Test Strategy
- **FR-065**: Test pyramid: Unit (70%) → Integration (20%) → E2E (10%)
- **FR-066**: Test data management (fixtures, factories, seeding)
- **FR-067**: Parallel test execution (CI pipeline)
- **FR-068**: Flaky test detection and quarantine

#### 5.4.2 Quality Gates (All Must Pass)
- **FR-069**: TypeScript strict mode - zero errors
- **FR-070**: ESLint - zero warnings
- **FR-071**: Unit test coverage ≥ 80% (lines, branches, functions)
- **FR-072**: Integration tests - 100% pass
- **FR-073**: E2E tests - 100% pass on critical paths
- **FR-074**: Accessibility audit (axe-core) - zero violations AA
- **FR-075**: Performance budget (Lighthouse) - Performance ≥ 90, Accessibility ≥ 95, Best Practices ≥ 90, SEO ≥ 90
- **FR-076**: Security scan (npm audit, Snyk, OWASP ZAP) - zero critical/high
- **FR-077**: Bundle size budget - JS < 200KB gzipped, CSS < 50KB

#### 5.4.3 Specialized Testing
- **FR-078**: Cross-browser testing (Chrome, Firefox, Safari, Edge)
- **FR-079**: Device testing (mobile, tablet, desktop viewports)
- **FR-080**: Network throttling (3G, 4G, offline)
- **FR-081**: Load testing (k6) for dashboards/portals
- **FR-082**: Chaos testing for AI systems (adversarial inputs)

### 5.5 DevOps & Deployment Department

#### 5.5.1 Multi-Target Deployment
- **FR-083**: Vercel (Next.js native, edge functions)
- **FR-084**: Cloudflare Pages (edge, workers, D1, R2)
- **FR-085**: Netlify (forms, functions, edge)
- **FR-086**: Railway (containers, databases, background workers)
- **FR-087**: VPS (Docker Compose, Kubernetes, full control)

#### 5.5.2 Deployment Pipeline
- **FR-088**: Preview deployments for every PR
- **FR-089**: Staging environment (auto-deploy from main)
- **FR-090**: Production deployment (manual approval gate)
- **FR-091**: Blue-green / rolling deployments for zero-downtime
- **FR-092**: Automated rollback on health check failure

#### 5.5.3 Configuration Management
- **FR-093**: Environment variables per environment (Vault/1Password)
- **FR-094**: Feature flags (LaunchDarkly style or custom)
- **FR-095**: Database migrations (run before deploy, rollback on failure)
- **FR-096**: SSL/TLS certificate management (auto-renewal)

#### 5.5.4 Post-Deployment Automation
- **FR-097**: Analytics setup (GA4, GTM, custom events)
- **FR-098**: Form handling (Formspree, Netlify Forms, custom)
- **FR-099**: Monitoring (uptime, performance, errors - Sentry)
- **FR-100**: SEO (sitemap.xml, robots.txt, structured data, meta tags)
- **FR-101**: Search console submission
- **FR-102**: CDN cache invalidation

### 5.6 Support & Maintenance Department

#### 5.6.1 Monthly Health Checks (Automated)
- **FR-103**: SSL certificate validity & expiry
- **FR-104**: Performance regression (Lighthouse CI comparison)
- **FR-105**: Uptime monitoring (99.9% target)
- **FR-106**: Broken link detection (internal + external)
- **FR-107**: SEO health (indexing, core web vitals, rankings)
- **FR-108**: Security headers, dependency vulnerabilities
- **FR-109**: Dependency updates (automated PRs for minor/patch)

#### 5.6.2 Client Reporting
- **FR-110**: Monthly maintenance report (PDF + dashboard)
- **FR-111**: Metrics: Uptime, Performance, Security, Updates, Issues Resolved
- **FR-112**: Upsell recommendations based on usage/analytics
- **FR-113**: Client portal with ticket system

#### 5.6.3 Incident Response
- **FR-114**: Alert routing (PagerDuty → Support Agent → Owner)
- **FR-115**: Auto-mitigation for common issues (cache clear, restart)
- **FR-116**: Post-incident report template
- **FR-117**: SLA tracking (response time, resolution time)

## 6. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Project Setup Time** | <10 minutes from contract |
| **Design Phase** | 3-7 days (Starter), 7-14 days (Business/Premium) |
| **Development Phase** | 7-21 days based on package |
| **QA Phase** | 2-5 days |
| **Deployment Time** | <15 minutes |
| **Maintenance Check Duration** | <30 minutes per site |
| **Incident Response** | <15 min acknowledgment, <1hr resolution (critical) |
| **Code Quality** | All gates 100% pass |
| **Client Satisfaction** | >4.5/5 on delivery survey |

## 7. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  DEVELOPMENT PIPELINE SYSTEM                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                               │
│  │  CONTRACT    │◄──── Signed contract from Sales               │
│  │  INGESTION   │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              PROJECT ORCHESTRATOR (LangGraph)              │   │
│  │  Create Project → Parse Scope → Generate WBS → Assign     │   │
│  └──────────────┬────────────────────────────────────────────┘   │
│                 │                                                 │
│   ┌─────────────┼─────────────┐                                   │
│   ▼             ▼             ▼                                   │
│┌────────┐  ┌────────┐  ┌────────┐                                 │
││ DESIGN │  │  DEV   │  │  QA    │  (Parallel where possible)      │
││ PHASE  │  │ PHASE  │  │ PHASE  │                                 │
│└────┬───┘  └────┬───┘  └────┬───┘                                 │
│     │           │           │                                     │
│     └───────────┼───────────┘                                     │
│                 ▼                                                 │
│        ┌────────────────┐                                         │
│        │  DEPLOYMENT    │                                         │
│        │  PIPELINE      │                                         │
│        └───────┬────────┘                                         │
│                │                                                   │
│                ▼                                                   │
│        ┌────────────────┐                                         │
│        │  MAINTENANCE   │                                         │
│        │  SYSTEM        │                                         │
│        └────────────────┘                                         │
│                                                                  │
│  AGENT COORDINATION VIA MESSAGE BUS                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ PM Agent│ │Design   │ │Dev Agent│ │QA Agent │ │DevOps   │   │
│  │         │ │Agent    │ │         │ │         │ │Agent    │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
│       │           │           │           │           │         │
│       └───────────┼───────────┼───────────┼───────────┘         │
│                   ▼           ▼           ▼                     │
│          ┌─────────────────────────────────────┐               │
│          │        SHARED PROJECT STATE         │               │
│          │  (PostgreSQL + Redis + Object Store)│               │
│          └─────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

## 8. Data Models

### 8.1 Project
```python
class Project(BaseModel):
    project_id: UUID
    contract_id: UUID
    client_id: UUID
    name: str
    service_type: ServiceType  # WEBSITE, AUTOMATION, AI_CHATBOT, AI_SYSTEM
    package: PackageTier  # STARTER, BUSINESS, PREMIUM, ENTERPRISE, CUSTOM
    
    # Scope
    scope: ProjectScope
    wbs: WorkBreakdownStructure
    
    # Timeline
    timeline: ProjectTimeline
    started_at: Optional[datetime]
    estimated_completion: datetime
    actual_completion: Optional[datetime]
    
    # Status
    status: ProjectStatus  # PLANNING, DESIGN, DEVELOPMENT, QA, DEPLOYING, LIVE, MAINTENANCE, COMPLETED
    phase: ProjectPhase
    progress_pct: float  # 0-100
    
    # Assignment
    pm_agent_id: str
    designer_agent_id: Optional[str]
    developer_agent_ids: List[str]
    qa_agent_id: Optional[str]
    devops_agent_id: Optional[str]
    support_agent_id: Optional[str]
    
    # Repositories & Environments
    github_repo: Optional[str]
    preview_url: Optional[str]
    staging_url: Optional[str]
    production_url: Optional[str]
    
    # Metrics
    velocity: float  # points/sprint
    quality_score: float  # 0-100
    client_satisfaction: Optional[float]
    
    # Financial
    contract_value: int
    invoiced_amount: int
    collected_amount: int
    
    created_at: datetime
    updated_at: datetime
```

### 8.2 Task
```python
class Task(BaseModel):
    task_id: UUID
    project_id: UUID
    parent_task_id: Optional[UUID]  # For hierarchy
    
    # Classification
    type: TaskType  # DESIGN, FRONTEND, BACKEND, API, DATABASE, TESTING, DEVOPS, DOCS
    department: DepartmentType
    priority: TaskPriority
    
    # Content
    title: str
    description: str
    acceptance_criteria: List[str]
    technical_notes: Optional[str]
    
    # Estimation
    estimated_points: int  # Story points
    estimated_hours: float
    actual_hours: float
    
    # Status
    status: TaskStatus  # TODO, IN_PROGRESS, IN_REVIEW, BLOCKED, DONE, CANCELLED
    assignee_agent_id: Optional[str]
    
    # Dependencies
    depends_on: List[UUID]
    blocks: List[UUID]
    
    # Git Integration
    branch_name: Optional[str]
    pr_url: Optional[str]
    commit_shas: List[str]
    
    # Quality
    code_review_status: ReviewStatus
    test_status: TestStatus
    qa_notes: Optional[str]
    
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: datetime
```

### 8.3 Deployment
```python
class Deployment(BaseModel):
    deployment_id: UUID
    project_id: UUID
    environment: Environment  # PREVIEW, STAGING, PRODUCTION
    target: DeploymentTarget  # VERCEL, CLOUDFLARE, NETLIFY, RAILWAY, VPS
    
    # Source
    git_ref: str  # branch, tag, commit
    commit_sha: str
    
    # Status
    status: DeploymentStatus  # QUEUED, BUILDING, DEPLOYING, HEALTH_CHECK, SUCCESS, FAILED, ROLLED_BACK
    
    # Build
    build_logs_url: Optional[str]
    build_duration_seconds: float
    build_artifacts: List[str]
    
    # Health Checks
    health_checks: List[HealthCheck]
    all_healthy: bool
    
    # Rollback
    rolled_back_from: Optional[UUID]
    rollback_reason: Optional[str]
    
    # URLs
    deployment_url: str
    inspector_url: Optional[str]
    
    triggered_by: str  # agent_id or "manual"
    created_at: datetime
    completed_at: Optional[datetime]
```

### 8.4 Maintenance Check
```python
class MaintenanceCheck(BaseModel):
    check_id: UUID
    project_id: UUID
    check_type: MaintenanceCheckType  # SSL, PERFORMANCE, UPTIME, LINKS, SEO, SECURITY, DEPENDENCIES
    status: CheckStatus  # PASSED, WARNING, FAILED, AUTO_FIXED
    
    # Results
    score: Optional[float]  # 0-100
    previous_score: Optional[float]
    details: Dict[str, Any]
    issues_found: List[MaintenanceIssue]
    auto_fixed: List[str]
    
    # Report
    report_generated: bool
    report_url: Optional[str]
    client_notified: bool
    
    run_at: datetime
    duration_seconds: float
```

## 9. API Contracts

### 9.1 Project Management
```
POST   /api/v1/projects
GET    /api/v1/projects?status=active&client_id={id}
GET    /api/v1/projects/{project_id}
PUT    /api/v1/projects/{project_id}
GET    /api/v1/projects/{project_id}/timeline
GET    /api/v1/projects/{project_id}/progress
GET    /api/v1/projects/{project_id}/burndown
```

### 9.2 Task Management
```
POST   /api/v1/projects/{project_id}/tasks
GET    /api/v1/projects/{project_id}/tasks?status=in_progress&assignee={agent}
PUT    /api/v1/tasks/{task_id}
POST   /api/v1/tasks/{task_id}/start
POST   /api/v1/tasks/{task_id}/complete
POST   /api/v1/tasks/{task_id}/block
GET    /api/v1/tasks/{task_id}/dependencies
```

### 9.3 Design & Development
```
POST   /api/v1/projects/{project_id}/design/handoff
GET    /api/v1/projects/{project_id}/design/specs
POST   /api/v1/projects/{project_id}/code/review
GET    /api/v1/projects/{project_id}/code/quality
POST   /api/v1/projects/{project_id}/tests/run
GET    /api/v1/projects/{project_id}/tests/results
```

### 9.4 Deployment
```
POST   /api/v1/projects/{project_id}/deploy
GET    /api/v1/deployments/{deployment_id}
GET    /api/v1/projects/{project_id}/deployments
POST   /api/v1/deployments/{deployment_id}/rollback
GET    /api/v1/projects/{project_id}/environments
```

### 9.5 Maintenance
```
POST   /api/v1/projects/{project_id}/maintenance/run
GET    /api/v1/maintenance/checks/{check_id}
GET    /api/v1/projects/{project_id}/maintenance/history
GET    /api/v1/projects/{project_id}/maintenance/report/latest
POST   /api/v1/maintenance/issues/{issue_id}/resolve
```

## 10. UI/UX Specifications

### 10.1 Project Dashboard (Owner)
- **Project grid**: Cards with status, progress, timeline, health indicators
- **Detail view**: Timeline (Gantt), task board, deployments, maintenance history
- **Client view toggle**: Simplified progress for client sharing

### 10.2 Agent Workbench (Per Department)
- **Task queue**: Prioritized, filterable, with context (specs, designs, related tasks)
- **Work panel**: Code editor (Dev), Design specs (Design), Test runner (QA), Deploy controls (DevOps)
- **Collaboration**: Comments, mentions, handoff buttons

### 10.3 Client Portal
- **Progress tracker**: Visual timeline with completed/upcoming milestones
- **Deliverables**: Approved designs, preview URLs, final deliverables
- **Support**: Ticket submission, status, maintenance reports
- **Billing**: Invoices, payments, upcoming renewals

## 11. Component Library

- `ProjectCard` - Status badge, progress ring, timeline, health
- `GanttChart` - Interactive, zoomable, dependency lines
- `TaskBoard` - Kanban with swimlanes by department
- `CodeReviewPanel` - Diff view, comments, approval
- `TestResultsDashboard` - Suite summary, coverage, flaky tests
- `DeploymentTimeline` - History with status, rollback buttons
- `MaintenanceReport` - Score cards, issue list, trend charts
- `ClientPortalLayout` - Navigation, progress header, content tabs

## 12. Motion & Animation

| Interaction | Animation | Duration |
|-------------|-----------|----------|
| Task status change | Color transition + checkmark | 300ms |
| Gantt bar drag | Ghost preview + snap | 200ms |
| Deployment progress | Progress bar + log tail | Real-time |
| Test result update | Pulse green/red | 400ms |
| Maintenance score change | Gauge animate | 600ms |
| Panel collapse/expand | Height + fade | 250ms |

## 13. Accessibility

- All dashboards keyboard navigable
- Screen reader announcements for status changes
- Color-blind safe status indicators (icons + colors)
- High contrast mode for code/design views
- Focus management in complex panels
- Reduced motion for animations

## 14. Performance Budgets

| Operation | Budget |
|-----------|--------|
| Project creation | <30s |
| Task board load (500 tasks) | <1s |
| Code review diff (1000 lines) | <2s |
| Test suite run (full) | <10 min |
| Deployment (build + deploy) | <15 min |
| Maintenance check (single site) | <30s |
| Client portal load | <1.5s |

## 15. Security Requirements

- **Code**: SAST/DAST in pipeline, dependency scanning, secrets detection
- **Infrastructure**: IaC scanning, least privilege, network policies
- **Deployments**: Signed artifacts, provenance verification (SLSA)
- **Access**: Short-lived tokens, audit all deployment actions
- **Data**: Client data encrypted, PII minimized in repos
- **Compliance**: SOC 2 controls, evidence collection automated

## 16. Testing Strategy

### 16.1 Unit Tests
- WBS generation from scope
- Task dependency resolution
- Timeline calculation with constraints
- Deployment health check logic
- Maintenance scoring algorithms

### 16.2 Integration Tests
- Full project lifecycle (contract → live)
- Multi-agent handoffs (Design → Dev → QA → Deploy)
- Rollback scenarios
- Maintenance auto-fix verification

### 16.3 Contract Tests
- GitHub/GitLab API integration
- Vercel/Cloudflare/Netlify/Railway APIs
- Monitoring webhooks (Sentry, UptimeRobot)

### 16.4 Quality Gate Tests
- Lighthouse CI thresholds enforced
- Accessibility regression detection
- Performance regression detection
- Security scan false positive rate <5%

## 17. Deployment Strategy

### 17.1 Agent Deployment
- **PM Agent**: Single instance (stateful coordination)
- **Design Agent**: Stateless, scale to 3
- **Dev Agent**: Stateful (repo access), 1 per concurrent project
- **QA Agent**: Stateless, scale to 5 (parallel test execution)
- **DevOps Agent**: Single per target platform
- **Support Agent**: Single instance, event-driven

### 17.2 Infrastructure
- **Git**: GitHub Organization with repo per project
- **CI/CD**: GitHub Actions (primary) + custom runners
- **Preview**: Vercel/Netlify preview deployments
- **Staging**: Dedicated environment per project
- **Production**: Client-owned or agency-managed

### 17.3 Secrets Management
- **1Password/Vault** for all credentials
- **Per-project** environment variable sets
- **Rotation** automated for cloud provider tokens

## 18. Monitoring & Observability

### 18.1 Metrics
- `project_duration_days` (histogram by package)
- `phase_duration_days` (histogram by phase)
- `task_completion_rate` (gauge by department)
- `deployment_success_rate` (gauge by target)
- `deployment_frequency` (counter)
- `lead_time_for_changes` (histogram)
- `mean_time_to_recovery` (histogram)
- `change_failure_rate` (gauge)
- `maintenance_check_pass_rate` (gauge by type)
- `client_satisfaction_score` (gauge)

### 18.2 Logs
- Structured logs for all agent actions
- Deployment logs with correlation IDs
- Test execution logs (pass/fail, duration)
- Maintenance check details

### 18.3 Alerts
| Alert | Condition | Severity |
|-------|-----------|----------|
| ProjectStalled | No progress > 3 days | High |
| DeploymentFailed | Production deploy failed | Critical |
| QualityGateFailed | Any gate failed | High |
| MaintenanceCheckFailed | Critical check failed (SSL, uptime) | Critical |
| SLAAtRisk | Incident response > 30 min | High |
| ClientUnhappy | Satisfaction < 3/5 | Medium |

## 19. Rollback & Recovery

- **Code rollback**: Git revert + redeploy (<10 min)
- **Database rollback**: Migration down + backup restore (<30 min)
- **Deployment rollback**: Platform native rollback (<5 min)
- **Full disaster**: Backup region failover (<1 hr RTO)
- **Data loss**: Point-in-time recovery (RPO < 5 min)

## 20. Open Questions & Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AI code quality variance | High | High | Strict quality gates, human review for complex logic |
| Design-Dev handoff friction | Medium | Medium | Shared design tokens, Storybook, automated spec generation |
| Third-party API changes | Medium | High | Version pinning, adapter pattern, monitoring |
| Deployment platform limits | Low | Medium | Multi-target strategy, abstraction layer |
| Client scope creep | High | Medium | Change request process, fixed-scope contracts |
| Talent dependency (human review) | Medium | Medium | Reduce human gates, improve AI quality |
| Security vulnerability in generated code | Low | Critical | SAST in pipeline, security-trained models |
| Maintenance scaling | Medium | Low | Automation-first, self-healing where possible |