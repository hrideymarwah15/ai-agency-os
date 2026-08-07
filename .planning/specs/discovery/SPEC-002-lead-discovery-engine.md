# SPEC-002: Lead Discovery Engine

## 1. Executive Summary

The Lead Discovery Engine continuously discovers businesses most likely to purchase agency services by scraping and analyzing data from 15+ sources across search engines, business directories, social platforms, startup platforms, community platforms, and job platforms. It enriches each business with 30+ data points, scores them using a weighted algorithm, and feeds qualified leads into the sales pipeline.

## 2. Problem Statement

Manual lead generation is slow, inconsistent, and doesn't scale. Agencies need a systematic way to:
- Discover businesses with genuine need for services
- Assess website/automation/AI maturity automatically
- Prioritize outreach by conversion probability
- Enrich contact data for personalized outreach
- Operate continuously without human bottlenecks

## 3. User Personas

| Persona | Role | Needs |
|---------|------|-------|
| **Lead Hunter Agent** | AI Department | Continuous lead stream; enrichment; scoring; deduplication |
| **Sales Agent** | AI Department | Qualified leads with context; contact info; pain points |
| **CEO Agent** | AI Orchestrator | Pipeline volume targets; source quality metrics |
| **Owner** | Human | Dashboard visibility; source configuration; compliance |

## 4. User Journeys

### Journey 1: Daily Discovery Cycle
```
Scheduler triggers → Market Scanner selects sources → Lead Collector scrapes → 
Business Analyzer enriches → Opportunity Ranking scores → Qualified leads stored
```

### Journey 2: Source-Specific Collection
```
Source config loaded → Rate limiter applied → Robots.txt checked → 
Crawler executes → Data normalized → Deduplication → Enrichment queue
```

### Journey 3: Website Intelligence Analysis
```
Business URL queued → Playwright crawler launches → Performance/SEO/Accessibility/UX audits run → 
Tech stack detected → Conversion flow mapped → Scores calculated → Results stored
```

## 5. Functional Requirements

### 5.1 Data Sources (15+ Sources)

#### Search Engines
- **FR-001**: Google Custom Search API (places, web search)
- **FR-002**: Google Maps Places API (local businesses)
- **FR-003**: Bing Search API (supplement)

#### Business Directories
- **FR-004**: Clutch (agencies, dev shops) - API/scraping
- **FR-005**: GoodFirms (service providers)
- **FR-006**: Yelp Fusion API (local businesses)
- **FR-007**: JustDial (India local)
- **FR-008**: IndiaMART (B2B India)

#### Social Platforms
- **FR-009**: LinkedIn Sales Navigator API / scraping
- **FR-010**: Instagram Graph API (business profiles)
- **FR-011**: Facebook Graph API (pages, ads library)
- **FR-012**: X/Twitter API v2 (profiles, tweets)
- **FR-013**: Threads API (when available)

#### Startup Platforms
- **FR-014**: Product Hunt API (new launches)
- **FR-015**: Wellfound (AngelList) API
- **FR-016**: Crunchbase API (respect licensing)
- **FR-017**: Angel ecosystem directories

#### Community Platforms
- **FR-018**: Reddit API (subreddits: r/startups, r/smallbusiness, etc.)
- **FR-019**: Indie Hackers (profiles, products)
- **FR-020**: Hacker News (Who is Hiring, Show HN)
- **FR-021**: Discord communities (via bot)

#### Job Platforms
- **FR-022**: LinkedIn Jobs API
- **FR-023**: Indeed API
- **FR-024**: RemoteOK API

### 5.2 Data Collected Per Business (30+ Fields)

| Category | Fields |
|----------|--------|
| **Identity** | Business Name, Legal Name, DBA, Industry, Sub-industry |
| **Contact** | Website, Primary Email, Phone, Contact Form URL |
| **Location** | Address, City, State, Country, Postal Code, Timezone |
| **Size** | Employee Count (range), Revenue Estimate, Funding Stage |
| **Social** | LinkedIn URL, Instagram, Facebook, X, Threads, YouTube |
| **Technical** | Technology Stack, CMS, Hosting Provider, CDN, Analytics |
| **Web Performance** | Traffic Estimate, SEO Score, Performance Score, Accessibility Score, Mobile Score |
| **Domain** | Domain Age, SSL Grade, DNS Health |
| **Reputation** | Google Rating, Review Count, Review Sentiment, Clutch Rating |
| **Signals** | Pain Points (detected), Growth Signals, Hiring Activity, Tech Debt Indicators |
| **Budget** | Estimated Budget Range, Decision Maker Title, Decision Maker LinkedIn |
| **Services** | Potential Services (matched), Priority Score (0-100) |

### 5.3 Website Intelligence Crawler

#### Performance Analysis
- **FR-025**: Core Web Vitals (LCP, FID, CLS, INP, TTFB)
- **FR-026**: Lighthouse Performance Score (0-100)
- **FR-027**: Resource optimization (images, JS, CSS, fonts)
- **FR-028**: Server response times, caching headers

#### Accessibility Audit
- **FR-029**: axe-core automated audit (WCAG 2.1 AA)
- **FR-030**: Color contrast, ARIA, keyboard nav, alt text, form labels
- **FR-031**: Accessibility score (0-100)

#### SEO Analysis
- **FR-032**: Meta tags (title, description, OG, Twitter cards)
- **FR-033**: Heading structure (H1-H6 hierarchy)
- **FR-034**: Structured data (JSON-LD, Microdata)
- **FR-035**: Sitemap.xml, robots.txt, canonical URLs
- **FR-036**: Indexability, crawlability, internal linking
- **FR-037**: Keyword analysis (content gaps)
- **FR-038**: Backlink profile summary (via API)

#### UX/Design Quality
- **FR-039**: Visual hierarchy analysis
- **FR-040**: Mobile responsiveness (breakpoints)
- **FR-041**: Conversion flow mapping (forms, CTAs, funnels)
- **FR-042**: Design consistency (colors, spacing, typography)
- **FR-043**: Trust signals (testimonials, badges, certifications)

#### Technical Detection
- **FR-044**: CMS detection (WordPress, Webflow, Shopify, etc.)
- **FR-045**: Framework detection (React, Vue, Next.js, etc.)
- **FR-046**: Hosting/CDN detection
- **FR-047**: Analytics/Tracking detection (GA, GTM, Hotjar, etc.)
- **FR-048**: Security headers (CSP, HSTS, X-Frame-Options)
- **FR-049**: Broken link detection (internal + external)
- **FR-050**: Form detection and validation testing

### 5.4 Automation Opportunity Detector

| Industry | Pattern | Recommendation |
|----------|---------|----------------|
| Restaurant | No online booking system | Booking Automation (WhatsApp/Web) |
| Clinic | Manual appointment scheduling | AI Receptionist + Calendar Sync |
| School | Paper-based admissions | Admissions Automation Portal |
| Agency | Manual client onboarding | CRM Automation + Workflows |
| Real Estate | Manual lead follow-up | AI Sales Bot + CRM |
| E-commerce | Manual order processing | Order Automation + Inventory Sync |
| Coaching | Manual scheduling/payments | Booking + Payment Automation |

**FR-051**: Pattern matching engine with configurable rules per industry
**FR-052**: ROI estimation based on time savings × hourly cost × frequency
**FR-053**: Confidence scoring for each recommendation

### 5.5 AI Opportunity Detector

| Signal | Detection Method | Recommendation |
|--------|------------------|----------------|
| No chatbot | DOM analysis + keyword search | Customer Support Bot |
| No FAQ | Content analysis | FAQ Assistant |
| No CRM | Tech stack detection | CRM Implementation |
| No analytics | Script detection | Analytics Setup |
| Poor support response | Social monitoring | AI Support Bot |
| Manual workflows | Job postings + content | Workflow Automation |
| No knowledge base | Site structure analysis | Internal Knowledge Assistant |

**FR-054**: Heuristic + ML-based detection
**FR-055**: Industry-specific opportunity templates
**FR-056**: Expected ROI calculation per opportunity

### 5.6 Lead Scoring Engine

**Weighted Algorithm (Total: 100%)**

| Factor | Weight | Sub-factors |
|--------|--------|-------------|
| Website Quality | 20% | Performance, Accessibility, SEO, UX, Design |
| SEO Maturity | 15% | Technical SEO, Content, Authority, Local SEO |
| Growth Signals | 20% | Hiring, Funding, Traffic growth, Social growth, New locations |
| Company Size | 15% | Employees, Revenue, Funding (sweet spot: 10-200 employees) |
| Automation Potential | 15% | Manual processes detected, Repetitive workflows, Scale |
| AI Potential | 10% | Chatbot missing, FAQ missing, Knowledge base missing, Support volume |
| Budget Estimate | 5% | Industry benchmarks, Company size, Growth stage |

**FR-057**: Configurable weights per service vertical
**FR-058**: Score normalization (0-100)
**FR-059**: Tier classification: Hot (80+), Warm (60-79), Cold (40-59), Raw (<40)

### 5.7 Deduplication & Enrichment
- **FR-060**: Fuzzy matching on name + domain + phone + address
- **FR-061**: Master record creation with source lineage
- **FR-062**: Incremental enrichment (only missing fields)
- **FR-063**: Contact discovery (Hunter.io, Apollo, Clearbit style)
- **FR-064**: Decision maker identification (LinkedIn title matching)

## 6. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Discovery Rate** | 500+ businesses/day |
| **Enrichment Coverage** | >80% for top 20 fields |
| **Scoring Accuracy** | >70% correlation with close rate |
| **Source Uptime** | >95% per source |
| **Rate Limit Compliance** | 100% (respect all API limits) |
| **Robots.txt Compliance** | 100% |
| **Data Freshness** | <30 days for top 1000 leads |
| **Deduplication Rate** | >95% duplicate detection |

## 7. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LEAD DISCOVERY ENGINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   SCHEDULER  │───►│  SOURCE      │───►│  COLLECTOR   │      │
│  │  (Daily/     │    │  REGISTRY    │    │  WORKERS     │      │
│  │   Cron)      │    │  (15+ sources)│   │  (Parallel)  │      │
│  └──────────────┘    └──────────────┘    └──────┬───────┘      │
│                                                  │               │
│                    ┌──────────────┐              │               │
│                    │  RATE LIMIT  │◄─────────────┘               │
│                    │  & COMPLIANCE │                             │
│                    └──────┬───────┘                              │
│                           │                                       │
│              ┌────────────┼────────────┐                          │
│              ▼            ▼            ▼                          │
│       ┌───────────┐ ┌───────────┐ ┌───────────┐                  │
│       │  SEARCH   │ │ DIRECTORY │ │  SOCIAL   │  ...             │
│       │  ENGINES  │ │  SOURCES  │ │  PLATFORMS│                  │
│       └─────┬─────┘ └─────┬─────┘ └─────┬─────┘                  │
│             │             │             │                          │
│             └─────────────┼─────────────┘                          │
│                           ▼                                       │
│                    ┌──────────────┐                               │
│                    │  NORMALIZER  │                               │
│                    │  (Unified    │                               │
│                    │   Schema)    │                               │
│                    └──────┬───────┘                               │
│                           │                                       │
│                    ┌──────┴───────┐                               │
│                    │ DEDUPLICATION │                               │
│                    │  ENGINE       │                               │
│                    └──────┬───────┘                               │
│                           │                                       │
│              ┌────────────┼────────────┐                          │
│              ▼            ▼            ▼                          │
│       ┌───────────┐ ┌───────────┐ ┌───────────┐                  │
│       │  WEBSITE  │ │  ENRICHMENT│ │  SCORING  │                 │
│       │INTELLIGENCE│ │  PIPELINE │ │  ENGINE   │                 │
│       │  CRAWLER  │ │ (Contact, │ │ (Weighted │                 │
│       │(Playwright)│ │  Social,  │ │ Algorithm)│                 │
│       └─────┬─────┘ │  Tech)    │ └─────┬─────┘                  │
│             │       └───────────┘       │                          │
│             │                           │                          │
│             └───────────────┬───────────┘                          │
│                             ▼                                       │
│                    ┌──────────────┐                               │
│                    │  LEAD STORE  │                               │
│                    │ (PostgreSQL + │                               │
│                    │  pgvector)   │                               │
│                    └──────┬───────┘                               │
│                           │                                       │
│                    ┌──────┴───────┐                               │
│                    │  OPPORTUNITY │                               │
│                    │  DETECTORS   │                               │
│                    │ (Auto + AI)  │                               │
│                    └──────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

## 8. Data Models

### 8.1 Source Configuration
```python
class DataSourceConfig(BaseModel):
    source_id: str
    name: str
    type: SourceType  # SEARCH, DIRECTORY, SOCIAL, STARTUP, COMMUNITY, JOBS
    enabled: bool
    priority: int  # 1-10
    rate_limit: RateLimitConfig
    auth: AuthConfig
    selectors: SelectorConfig  # CSS/XPath/JSON paths
    schedule: CronSchedule
    compliance: ComplianceConfig
    cost_per_request: float
    max_daily_requests: int
```

### 8.2 Business Lead
```python
class BusinessLead(BaseModel):
    lead_id: UUID
    source_ids: List[str]  # Provenance
    master_record: bool
    
    # Identity
    business_name: str
    legal_name: Optional[str]
    industry: IndustryCategory
    sub_industry: Optional[str]
    
    # Contact
    website: Optional[HttpUrl]
    email: Optional[EmailStr]
    phone: Optional[str]
    contact_form_url: Optional[HttpUrl]
    
    # Location
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: str = "India"
    postal_code: Optional[str]
    timezone: Optional[str]
    
    # Size
    employee_count_min: Optional[int]
    employee_count_max: Optional[int]
    revenue_estimate: Optional[RevenueRange]
    funding_stage: Optional[FundingStage]
    
    # Social
    linkedin_url: Optional[HttpUrl]
    instagram_url: Optional[HttpUrl]
    facebook_url: Optional[HttpUrl]
    twitter_url: Optional[HttpUrl]
    
    # Technical
    tech_stack: List[Technology]
    cms: Optional[CMSType]
    hosting_provider: Optional[str]
    analytics_tools: List[str]
    
    # Web Scores (0-100)
    performance_score: Optional[float]
    accessibility_score: Optional[float]
    seo_score: Optional[float]
    ux_score: Optional[float]
    mobile_score: Optional[float]
    
    # Domain
    domain_age_days: Optional[int]
    ssl_grade: Optional[SSLGrade]
    
    # Reputation
    google_rating: Optional[float]
    review_count: Optional[int]
    review_sentiment: Optional[SentimentScore]
    clutch_rating: Optional[float]
    
    # Signals
    pain_points: List[PainPoint]
    growth_signals: List[GrowthSignal]
    hiring_activity: HiringLevel
    tech_debt_indicators: List[str]
    
    # Budget & Decision Maker
    estimated_budget_min: Optional[int]  # INR
    estimated_budget_max: Optional[int]
    decision_maker_name: Optional[str]
    decision_maker_title: Optional[str]
    decision_maker_linkedin: Optional[HttpUrl]
    
    # Scoring
    priority_score: float  # 0-100
    score_breakdown: ScoreBreakdown
    tier: LeadTier
    
    # Opportunities
    automation_opportunities: List[AutomationOpportunity]
    ai_opportunities: List[AIOpportunity]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    last_enriched_at: Optional[datetime]
    enrichment_version: int
```

### 8.3 Website Intelligence Report
```python
class WebsiteIntelligenceReport(BaseModel):
    report_id: UUID
    lead_id: UUID
    url: HttpUrl
    crawled_at: datetime
    crawler_version: str
    
    # Core Web Vitals
    lcp: Optional[float]  # ms
    fid: Optional[float]  # ms
    cls: Optional[float]
    inp: Optional[float]  # ms
    ttfb: Optional[float]  # ms
    
    # Lighthouse Scores (0-100)
    performance_score: int
    accessibility_score: int
    best_practices_score: int
    seo_score: int
    pwa_score: Optional[int]
    
    # Detailed Audits
    performance_audit: PerformanceAudit
    accessibility_audit: AccessibilityAudit
    seo_audit: SEOAudit
    ux_audit: UXAudit
    
    # Technical
    tech_stack: TechStackDetection
    cms: CMSDetection
    hosting: HostingDetection
    analytics: AnalyticsDetection
    security_headers: SecurityHeaders
    
    # Issues
    broken_links: List[BrokenLink]
    forms: List[FormAnalysis]
    conversion_flows: List[ConversionFlow]
    
    # Raw Data
    html_size_kb: int
    resource_count: int
    request_count: int
    load_time_ms: int
```

### 8.4 Opportunity Models
```python
class AutomationOpportunity(BaseModel):
    opportunity_id: UUID
    lead_id: UUID
    category: AutomationCategory
    title: str
    description: str
    detected_pattern: str
    confidence: float  # 0-1
    estimated_hours_saved_monthly: float
    estimated_hourly_cost: float  # INR
    estimated_monthly_roi: float  # INR
    implementation_complexity: ComplexityLevel
    recommended_solution: str
    service_package: ServicePackage

class AIOpportunity(BaseModel):
    opportunity_id: UUID
    lead_id: UUID
    category: AICategory
    title: str
    description: str
    detected_signal: str
    confidence: float
    estimated_setup_cost: float  # INR
    estimated_monthly_value: float  # INR
    payback_months: float
    recommended_solution: str
    service_package: ServicePackage
```

## 9. API Contracts

### 9.1 Source Management
```
POST   /api/v1/sources
GET    /api/v1/sources
GET    /api/v1/sources/{source_id}
PUT    /api/v1/sources/{source_id}
DELETE /api/v1/sources/{source_id}
POST   /api/v1/sources/{source_id}/test
GET    /api/v1/sources/{source_id}/metrics
```

### 9.2 Lead Operations
```
GET    /api/v1/leads? tier=hot&limit=50&offset=0
GET    /api/v1/leads/{lead_id}
GET    /api/v1/leads/{lead_id}/intelligence
GET    /api/v1/leads/{lead_id}/opportunities
POST   /api/v1/leads/{lead_id}/re-enrich
POST   /api/v1/leads/{lead_id}/re-score
```

### 9.3 Discovery Control
```
POST   /api/v1/discovery/run
GET    /api/v1/discovery/status
POST   /api/v1/discovery/pause
POST   /api/v1/discovery/resume
GET    /api/v1/discovery/stats
```

### 9.4 Export & Integration
```
GET    /api/v1/leads/export?format=csv&tier=hot
GET    /api/v1/leads/export?format=json&sales_ready=true
POST   /api/v1/leads/push-to-crm
```

## 10. UI/UX Specifications

### 10.1 Lead Discovery Dashboard
- **Source health panel**: Green/yellow/red per source with last run, success rate, leads found
- **Pipeline funnel**: Raw → Enriched → Scored → Qualified → Hot
- **Geographic heatmap**: Lead density by city/state
- **Industry breakdown**: Bar chart of leads by industry
- **Score distribution**: Histogram of priority scores
- **Top opportunities table**: Sortable by ROI, confidence, tier

### 10.2 Lead Detail View
- **Header**: Business name, tier badge, priority score, last updated
- **Tabs**: Overview | Website Intelligence | Opportunities | Contact | History
- **Website Intelligence**: Visual score cards, Lighthouse-style metrics, issue list
- **Opportunities**: Cards with ROI, confidence, recommended service, "Create Proposal" action
- **Contact**: Enriched contact info with confidence indicators, "Verify" buttons

## 11. Component Library

- `SourceHealthCard` - Status, last run, success rate, leads today
- `LeadCard` - Name, industry, location, tier, score, top opportunity
- `ScoreBreakdownChart` - Horizontal bar chart with weight labels
- `WebVitalsGauge` - Circular gauge for each CWV metric
- `OpportunityCard` - Type, title, ROI, confidence, CTA
- `IndustryDistributionChart` - Treemap or bar chart
- `GeographicHeatmap` - Mapbox/Leaflet with lead clusters
- `EnrichmentProgress` - Stepper showing enrichment stages

## 12. Motion & Animation

| Interaction | Animation | Duration |
|-------------|-----------|----------|
| Lead card hover | Lift + shadow | 200ms |
| Score gauge fill | Arc draw | 800ms |
| Source status change | Pulse + color | 300ms |
| New lead appears | Slide in + highlight | 400ms |
| Tab switch | Cross-fade | 150ms |
| Data refresh | Skeleton → content | 300ms |

## 13. Accessibility

- All charts have text alternatives (data tables)
- Color-blind safe palettes for charts
- Keyboard navigation for all interactive elements
- Screen reader announcements for live updates
- Focus management in detail views
- High contrast mode for dashboard

## 14. Performance Budgets

| Operation | Budget |
|-----------|--------|
| Single source collection | <30s |
| Website crawl (single) | <60s |
| Full enrichment pipeline | <5 min/lead |
| Lead scoring | <100ms |
| Dashboard load (1000 leads) | <2s |
| Export CSV (10k leads) | <10s |
| API p99 (lead list) | <200ms |

## 15. Security Requirements

- **API Keys**: Stored in Vault, rotated quarterly
- **Scraping**: Respect robots.txt, rate limits, ToS
- **PII**: Email/phone encrypted at rest, masked in logs
- **Compliance**: GDPR Art. 17 (right to erasure), DPDP India
- **Data Retention**: Leads 2 years, Intelligence 1 year, Raw HTML 30 days
- **Access Control**: Only Lead Hunter + Sales agents + Owner

## 16. Testing Strategy

### 16.1 Unit Tests
- Source config validation
- Normalization transforms
- Deduplication algorithm (fuzzy matching)
- Scoring algorithm with fixtures
- Opportunity detection rules

### 16.2 Integration Tests
- End-to-end collection from test sources
- Playwright crawler against test sites
- Enrichment pipeline with mock APIs
- Lead store CRUD + vector search

### 16.3 Contract Tests
- Source API response schemas
- Lead schema validation
- Intelligence report schema

### 16.4 Compliance Tests
- Robots.txt respect verification
- Rate limit adherence
- PII handling verification
- Data retention policy enforcement

## 17. Deployment Strategy

### 17.1 Crawler Infrastructure
- **Playwright pool**: Kubernetes Deployment with 10-50 replicas
- **Queue**: Redis + BullMQ for crawl jobs
- **Browser**: Chrome headless in containers
- **Proxy rotation**: Residential proxy pool (optional)

### 17.2 Scaling
- **Horizontal**: Add collector workers based on queue depth
- **Vertical**: Increase browser pool for complex sites
- **Scheduled**: Scale down at night (IST 11pm-6am)

### 17.3 Monitoring
- **Crawl success rate** per source
- **Queue depth** and processing latency
- **Proxy health** and rotation
- **Cost per lead** by source

## 18. Monitoring & Observability

### 18.1 Metrics
- `leads_discovered_total` (counter by source, tier)
- `leads_enriched_total` (counter)
- `crawl_duration_seconds` (histogram)
- `enrichment_duration_seconds` (histogram)
- `scoring_duration_seconds` (histogram)
- `source_health` (gauge: 0/1)
- `queue_depth` (gauge)
- `cost_per_lead_inr` (gauge by source)

### 18.2 Logs
- Structured JSON with correlation_id
- Source, lead_id, stage, duration, success/error
- PII redacted (email→e***@d.com, phone→+91-***-***-1234)

### 18.3 Alerts
| Alert | Condition | Severity |
|-------|-----------|----------|
| SourceDown | Success rate <50% for 1hr | Critical |
| QueueBacklog | >5000 pending crawls | High |
| CrawlTimeout | >10% crawls >120s | Medium |
| EnrichmentFailure | >20% enrichment failures | High |
| CostSpike | Daily cost >2x 7-day avg | Medium |

## 19. Rollback & Recovery

- **Crawler crash**: Job re-queued with incremented retry count (max 3)
- **Enrichment failure**: Partial data saved, re-enrichment scheduled
- **Source API change**: Versioned selectors, fallback to previous version
- **Data corruption**: Point-in-time recovery from PostgreSQL WAL
- **Deduplication error**: Manual merge tool for master records

## 20. Open Questions & Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Source API changes | High | High | Versioned selectors, monitoring, fallback sources |
| Rate limit bans | Medium | High | Proxy rotation, exponential backoff, multiple API keys |
| Legal challenges (scraping) | Medium | Critical | Legal review, robots.txt compliance, ToS audit |
| Data quality decay | High | Medium | Re-enrichment schedule, freshness scoring |
| Cost overrun (APIs) | Medium | High | Daily budgets, cost per lead tracking, free tier optimization |
| Proxy IP burnout | Medium | Medium | Rotation, residential pools, request distribution |
| False positive opportunities | Medium | Medium | Confidence thresholds, human feedback loop |
| International compliance | Low | High | Geo-fencing, regional legal review |