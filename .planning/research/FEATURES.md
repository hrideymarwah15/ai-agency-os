# Feature Research

**Domain:** Autonomous AI-powered digital agency platform (AI Agency OS)
**Researched:** 2026-08-04
**Confidence:** MEDIUM (ecosystem feature sets well-documented across multiple sources; market-behavior claims from secondary sources; legal analysis is general guidance, not legal advice)

## Feature Landscape

Scope: lead discovery + website intelligence + scoring → autonomous sales/negotiation → proposals/contracts → payments → project delivery → maintenance/upsell, all under compliance guardrails (robots.txt, rate limits, anti-spam, auditable AI decisions). Benchmarked against GoHighLevel, HubSpot, AI SDRs (11x, Artisan, AiSDR, Regie), enrichment/sending stacks (Clay, Apollo, Hunter, Instantly, Smartlead), audit tools (Lighthouse/PSI, ProspectUp, SEOptimer, SE Ranking), agency reporting (AgencyAnalytics, DashThis), automation platforms (n8n, Make, Zapier).

### Table Stakes (Users Expect These)

Features the market treats as required. Missing these = product not credible as an agency OS.

#### A. Lead Discovery & Intelligence Pipeline

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-source lead collection with per-source config/registry | Every lead-gen tool ships this (Instantly Lead Finder, 11x 400M+ contact DB, Apollo). Source config, schedule, enable/disable, cost-per-lead tracking are baseline | HIGH | SPEC-002's 15+ sources is ambitious; ship 3-5 high-yield sources first (Google Places, JustDial, web search, directories). Source API churn is the #1 maintenance risk (SPEC-002 §20 risk table agrees) |
| Deduplication + master record with source lineage | Contact databases treat fuzzy dedupe (name+domain+phone) as core; provenance ("where did this come from") is now demanded for legal accountability — Instantly markets "data provenance transparency" for exactly this reason | MEDIUM | SPEC-002 FR-060/061 already spec'd. Lineage also feeds DPDP sourcing documentation (see Anti-Features) |
| Email discovery with verification + confidence signal | Hunter/Apollo/LeadScan all return a verification status (valid/risky/catch-all/unknown) or confidence score. Buyers compare hard-bounce rates: <1% best-in-class, <2% acceptable, >5% = sender reputation at risk (Apollo SLA benchmarks) | HIGH | Apollo's "confidence score" is a sourcing estimate, NOT a deliverability check; Hunter's SMTP check is find-time only. Industry practice: independent verification pass at send-time as the final gate. Catch-all and role-based (info@, support@) flagged, not sent |
| Data freshness management (re-verify + re-enrichment schedule) | B2B data decays fast; provider SLAs require re-verification within 90 days (best practice 30) plus suppression of stale records. "Nearly 4 in 10 CRM emails are garbage" (Prospeo); unverified lists lose ~22pp inbox placement at scale (Digital Bloom) | MEDIUM | SPEC-002 NFR (<30 days freshness for top 1000 leads) is above industry best practice — keep, but make re-verification incremental (only missing/changed fields) to control cost |
| Suppression list + opt-out handling (shared across channels) | Legal requirement (CAN-SPAM opt-outs within 10 business days; GDPR/DPDP immediate is best practice) and deliverability protection; Smartlead/Instantly auto-suppress globally | LOW-MEDIUM | Single source of truth across email/WhatsApp/LinkedIn so no re-contact ever happens (SPEC-003 campaign statuses already include OPTED_OUT) |
| Weighted, configurable lead scoring (0-100, tier classification) | GoHighLevel has rule-based scoring; HubSpot has predictive. Visible weight breakdown is standard in AI SDR stacks | MEDIUM | SPEC-002 FR-057/058/059 already defined (7 factors, Hot/Warm/Cold/Raw). Keep weights configurable per service vertical; validate against close rate (spec NFR: >70% correlation) |
| Source health monitoring + lead throughput metrics | Any scraping product needs per-source success rate, queue depth, cost-per-lead dashboards (SPEC-002 §18 already defines these) | MEDIUM | Also the early-warning system for source API changes/bans |
| Decision-maker identification (title matching, LinkedIn enrichment) | Standard in every SDR database (Apollo title filters, Hunter decision-maker lookups) | MEDIUM | Feeds outreach personalization tokens (SPEC-003 FR-002) |
| Contact form URL + phone capture as fallback contact | Tools surface all contact paths (email, phone, form, social) with confidence indicators | LOW | Reduces bounce risk; supports multi-channel outreach |

#### B. Website Intelligence (Audit)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Lighthouse-based audits: Performance, Accessibility, Best Practices, SEO + Core Web Vitals (LCP/FCP/TBT/CLS/SI) | This IS the industry standard: Google's PageSpeed Insights runs Lighthouse; every audit tool (SEOptimer, Sitechecker, Zutrix, ProspectUp) builds on or mirrors it. Performance weights (LH10): TBT 30%, LCP 25%, CLS 25%, FCP 10%, SI 10% (official Google docs) | MEDIUM | Use Lighthouse CI / PageSpeed Insights API rather than reimplementing. NOTE: SPEC-002 lists FID — FID was replaced by INP in March 2024; use INP |
| Score presentation: 0-100 bands (90+ good, 50-89 needs improvement, <50 poor), letter grades, color coding | Universal convention (Lighthouse bands; ProspectUp A-F letter grades; SE Ranking health score). Issues categorized critical/warning/notice with fix priority | LOW-MEDIUM | The proposal-facing "audit scorecard" (SPEC-003 FR-025/040) should mirror this visual language so prospects recognize it |
| Broken link detection (internal + external) | Every audit tool has it (Dead Link Checker, Zutrix, Sitechecker); easy crawl byproduct | LOW-MEDIUM | Include 404 + redirect chain checks (SPEC-002 FR-049) |
| Tech stack detection (CMS, ecommerce, booking/chat widgets, analytics, hosting/CDN) | ProspectUp fingerprints 30+ technologies; Wappalyzer is the de-facto standard. Feeds both scoring and opportunity detection | MEDIUM-HIGH | The single most important input for automation/AI opportunity detection (booking widget present? chat widget? analytics?) |
| SSL cert / security headers / HTTPS checks | Table stakes for any site checker (Sitechecker, Zutrix) | LOW | Cheap signal, included in Best Practices |
| SEO checks: meta tags, heading structure, structured data, sitemap/robots.txt, indexability, canonical | Standard crawl checks in every SEO audit tool | MEDIUM | SPEC-002 FR-032-036. Defer backlink analysis to v2 (paid APIs, low ROI for SMB lead qualification) |
| Recurring site monitoring (scheduled re-audits, change detection) | Audit tools sell scheduled crawls + monitoring (SE Ranking, Sitechecker); also feeds the Maintenance System | MEDIUM | Share the crawler with the Maintenance System — same engine, different cadence |

#### C. Sales & Outreach

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-touch outreach sequences with personalization tokens | Baseline in every sending tool (Instantly, Smartlead, Lemlist). 5-7 touches / 14-21 days is the standard playbook | MEDIUM-HIGH | SPEC-003 FR-010-013; spintax and A/B subject testing are expected companions |
| Follow-up automation (time-based + trigger-based: open/click) | Table stakes for sequences | MEDIUM | SPEC-003 FR-020/021; requires open/click tracking (part of deliverability infra) |
| Deliverability infrastructure: SPF/DKIM/DMARC, domain warm-up (2-3 weeks), per-inbox volume caps (30-50/day), bounce handling | Every serious tool owns or integrates sending infrastructure. Skipping warm-up is the most common deliverability killer; >5% bounce or >0.3% spam complaints (Google sender threshold, now a compliance benchmark) damages sender reputation | HIGH | Least glamorous, most critical piece. SPEC-003 alert "bounce >5% in 1hr = Critical" — with verify-before-send, steady-state bounce should be <1-2% |
| Reply classification + conversational handling (interested / not interested / later / referral / question / objection) | AI SDRs (11x, AiSDR, Artisan, Regie) all auto-classify replies; reply handling is where AI SDRs prove value vs plain sequencers | HIGH | SPEC-003 FR-015/016; confidence thresholds + escalation to owner on low confidence |
| Unsubscribe link + physical address + honest headers in every email | CAN-SPAM minimum (opt-out within 10 business days); GDPR/DPDP best practice is immediate; also reduces complaints | LOW | Non-negotiable; SPEC-003 FR-014 covers it |
| Meeting scheduling (Cal.com/Calendly-style) | Expected in every outreach stack | LOW | Use Cal.com (self-hostable, free) — aligns with budget constraint |
| CRM with pipeline stages + activity history | Core expectation (GHL, HubSpot, Pipedrive) | MEDIUM | SPEC-003 FR-018; status progression New → Contacted → Replied → Qualified → Meeting → Proposal → Negotiation → Closed Won/Lost |

#### D. Proposals, Contracts, Payments

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Proposal generation from templates (PDF/HTML/DOCX) with variable injection | Agency proposal tools (PandaDoc, Better Proposals, Qwilr) made this baseline; clients expect branded, structured proposals | MEDIUM | SPEC-003 FR-024-046. Audit-integrated proposals (scorecards + issue screenshots) are the differentiated format, but generation plumbing is standard |
| E-signature integration | Standard (DocuSign/HelloSign); self-hosted alternative: SignWell | LOW | Integration only; keep provider swappable |
| Contract generation from lawyer-approved templates with version control | Legal safety for any agency; version-controlled clause templates are standard in CLM tooling | MEDIUM | SPEC-003 FR-072-085; jurisdiction variants (India / International) |
| Owner approval gate before contract send | Non-negotiable for legal liability (SPEC-003 §15) and core to the product's trust story | LOW-MEDIUM | Infrastructure pattern: draft → pending_approval → approved → send. Same gate pattern reused for payments and out-of-guardrail commitments |
| Payment collection (Stripe/Razorpay) + invoices + payment reminders | Baseline for any services business | MEDIUM | SPEC-003 FR-076/077; milestone/50-50 schedules per contract |
| Recurring billing (maintenance, hosting, AI credits) | The business model requires it (PROJECT.md: every project carries recurring revenue); subscription billing is standard (Stripe Billing) | MEDIUM | Recurring revenue is the finance dashboard's core input |
| Finance dashboard: MRR/ARR + MRR movement (new/expansion/contraction/churned), churn (logo + revenue), NRR, LTV (gross-margin based), CAC, LTV:CAC, CAC payback | Standard SaaS/agency metrics (ChartMogul, Baremetrics, Maxio). Benchmarks: LTV:CAC 3:1 is the floor (median 3.6:1), CAC payback <12mo healthy (median worsened to 20mo), monthly churn <5% SMB / <2% enterprise, NRR >100% healthy | MEDIUM | ROADMAP M4.3 lists MRR/ARR, pipeline value, margin, LTV/CAC — all standard. Compute MRR from the recurring billing engine, not manually |
| Pipeline value by stage + deal forecasting | Expected in every CRM dashboard (GHL reporting, HubSpot forecasts) | MEDIUM | Derive from CRM pipeline stages |

#### E. Ops Dashboard (Owner Oversight)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Pipeline kanban with deal cards + stage columns | Table stakes (GHL, HubSpot, Pipedrive all lead with this) | MEDIUM | SPEC-003 §10.1; unlimited pipelines per service vertical |
| Unified activity feed / audit trail of agent actions | For an autonomous system this replaces the "team activity" view agencies expect (GHL has per-contact interaction history). Also the raw material for the AI decision log | MEDIUM-HIGH | Every agent action (research, send, classification, proposal version, negotiation turn) logged with agent ID, timestamp, rationale |
| Approval center: contracts, payments, out-of-guardrail negotiation, high-value deals | Human-in-the-loop is now the industry norm — 2026 market data shows fully autonomous AI SDRs (Artisan/11x) deployed as full replacements largely reverted to hybrid models (Miniloop, Knock, Instantly analyses) | HIGH | SPEC-003 FR-066-071 escalation triggers + FR-082 approval workflow. This is the trust mechanism that makes "autonomous" marketable |
| Agent/performance metrics: response rate, meeting rate, proposal rate, close rate, cycle time | Expected in sales platforms (GHL reports, Outreach) | MEDIUM | SPEC-003 §18 metrics; also validates scoring model |
| Cost per lead / per deal tracking | Needed to run an agency profitably; SPEC-002 §18 defines the metrics | MEDIUM | Free-tier budget constraint (PROJECT.md) makes cost control essential |

#### F. Client Success & Maintenance

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Automated monthly client reports (white-label, scheduled) | Category standard: AgencyAnalytics (80+ connectors, scheduled PDF/email reports, AI insight summaries), DashThis, Whatagraph. Agencies productize reporting as a margin line | MEDIUM | SPEC: maintenance system monthly checks (SSL, uptime, broken links, SEO, security, deps) → client report. White-label branding is expected, not a bonus |
| Uptime / SSL / performance monitoring with alerts | Table stakes for any managed-service agency (UptimeRobot category) | LOW-MEDIUM | Same monitoring feeds both maintenance system and report |
| Client portal / dashboard (live metrics view) | AgencyAnalytics/Databox offer live client dashboards; note: full GHL-style white-label SaaS mode is out of scope (PROJECT.md) — a read-only client report portal is the v1 shape | MEDIUM | Don't build a client-facing CRM; build a report portal |
| Client health scoring + churn prediction | Standard in CS platforms (Gainsight/ChurnZero category); feeds upsell engine | HIGH | v1.x — needs historical data to be meaningful |

#### G. Compliance Foundation (Non-Negotiable Layer)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| robots.txt respect + rate limiting per source | Crawler hygiene is baseline (SPEC-002 NFR: 100% compliance); also the legal good-faith signal | LOW | Check robots.txt per host before crawl; exponential backoff on limits |
| Verification-before-send gate in outreach | Industry-standard hygiene (BillionVerify/LeadScan/Tomba all sell "verify at send time"); protects sender reputation and avoids wasted spend | MEDIUM | Blocklist: catch-all, role-based, invalid, and >90-day-unverified addresses from cold sends |
| Privacy notice + data source disclosure in outreach (DPDP/GDPR) | India's DPDP Act requires informing data principals of purpose/categories/rights at first contact; GDPR legitimate-interest requires documented assessment | LOW | Every outreach email needs privacy-notice footer. Most US tools don't do this — being DPDP-first is a differentiator in the India market (see Differentiators) |
| Consent/source record keeping per contact (source, date, basis, preference history) | DPDP requires proof of consent/sourcing basis; GDPR requires lawful-basis documentation | MEDIUM | Store on the lead record; surfaces in audit log and erasure workflows |
| Data retention + erasure workflows (right to erasure/deletion) | GDPR Art. 17, DPDP rights; SPEC-002 §15 sets retention (leads 2y, intelligence 1y, raw HTML 30d) | MEDIUM | Deletion must propagate to suppression list + third-party stores |
| Auditable AI decision log | Differentiator today, but becoming expected as regulators (EU AI Act) and enterprise buyers demand AI accountability | MEDIUM | Every decision: prompt context, guardrail checks, output, approval status, agent ID. Also the debugging tool for agent behavior |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but where the product wins.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Opportunity detection with industry-specific ROI estimates ("your restaurant loses ₹X/month without online booking") | Audit tools (ProspectUp, Insites, SEOptimer) give scores and issues but NOT monetized opportunities matched to services. This converts "your site is slow" into "you're losing money — here's the fix we sell". The SPEC-002 pattern engine (restaurant booking, clinic appointments, school admissions) is unique to this product | HIGH | Depends on tech-stack detection + DOM analysis + industry templates. ROI formula: time saved × hourly cost × frequency (SPEC-002 FR-052) |
| Autonomous negotiation with hard guardrails + escalation | AI SDRs stop at meeting booking; no market tool negotiates price within limits, bundles services, or escalates out-of-guardrail requests to a human. This is the deepest part of the "autonomous agency" promise | HIGH | Guardrails are hard rules, not LLM judgment: never below min price, never change legal clauses, escalate on threshold (SPEC-003 FR-056-071). Requires negotiation-state machine + full conversation log |
| End-to-end autonomous pipeline (lead → proposal → contract → delivery → maintenance) | 11x/Artisan cover sales only; GHL automates but needs human operators at every stage; no product closes the loop through delivery and recurring revenue | HIGH | This is the product thesis (PROJECT.md Core Value). Phased: discovery+sales first, delivery/maintenance later |
| Pricing engine with min-price floor, margin math, and negotiation limits | No competitor prices agency work from hours×complexity×market×ROI with enforced floors; agencies run this in spreadsheets | MEDIUM | SPEC-003 §5.3; deterministic math + config, not AI guessing — AI only narrates the rationale |
| Audit report as a sales weapon (prospect-facing scorecard + free-audit lead capture) | The "free website audit" is the #1 agency lead-gen motion (Insites, SEOptimer, ProspectUp all built lead-gen widgets around it). Baked into proposals natively | MEDIUM-HIGH | SPEC-003 FR-025/026/039-042; include screenshots of issues |
| DPDP-first compliance design (India) | Global tools are GDPR/US-centric; Indian B2B outreach under DPDP needs privacy notices, sourcing records, and consent proof that US tools don't provide. PROJECT.md targets India (JustDial, IndiaMART, INR pricing) | MEDIUM | Build the compliance layer natively, not bolted on. Real, addressable market gap |
| Auditable AI decision log + approval gates as a trust brand | 2026 market data: buyers distrust black-box autonomous agents (Artisan reviews document "zero quality leads" complaints; hybrid is winning). A product that shows its work and asks permission is the credible version of "autonomous" | MEDIUM | Surface decision log in the owner dashboard, not just a database table |
| Client health + upsell/referral engine feeding automated proposals | CS platforms score health; CRM platforms track usage; nobody auto-generates the upsell proposal with pricing | HIGH | v2; depends on maintenance telemetry + proposal generator |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create legal, compliance, or reputational problems. Deliberately NOT build.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Mass cold email to purchased/scraped lists without consent checks | "Biggest list = most leads"; bought lists are cheap and fast | India's DPDP Act 2023 has NO GDPR-style "legitimate interest" escape: Section 7 "certain legitimate uses" is a closed list (numerus clausus) that does NOT include marketing. Marketing requires consent or Section 7(a) (data voluntarily provided for a specified purpose, no objection). Purchased lists carry no consent proof → exposure up to INR 250 crore (~$30M). Even where legal (US CAN-SPAM), unverified blasts kill sender reputation (bounce >5%, spam complaints >0.3% = Google blocklists) | Source leads from publicly listed business data (JustDial/IndiaMART listings, Google Places — contact provided voluntarily for business purposes, Section 7(a) path), verify every email before send, document sourcing, honor opt-outs immediately, seed-test new segments (200-500 contacts, measure 48h) |
| LinkedIn automation (browser bots: auto-connect, auto-message, profile-view blasts) | LinkedIn is where decision-makers are; tools like Dux-Soup/LinkedIn Helper are popular | LinkedIn User Agreement §8.2 explicitly bans scraping/bots/automation without written consent. Enforcement: account restriction/ban, cascading bans across accounts sharing IP/tool. Legal: hiQ v. LinkedIn — hiQ won the CFAA argument on public data but LOST on breach of contract ($500K judgment + permanent injunction, company closed); LinkedIn v. ProAPIs (2025) targets fake-account scraping (contract + fraud exposure). Login wall = contract attachment | Official LinkedIn API only (Sales Navigator via approved partner/API), human-in-loop for connection requests, inbound-first motions. Per PROJECT.md: LinkedIn direct API is already out of scope for v1 — keep it that way |
| Scraping logged-in platforms / fake accounts / paywalled data (Instagram, Facebook, X, Crunchbase premium) | Rich contact/activity data seems valuable | Meta v. Bright Data (2024) and hiQ established logged-out public scraping is defensible, but logged-in scraping breaches ToS (contract liability) and fake accounts add fraud exposure. GDPR/DPDP apply to personal data even if "public" — individual emails/phones/names are personal data with real compliance risk | Logged-out public data + official APIs + directories that publish business data. Reddit/HN/Product Hunt public APIs are safe. PROJECT.md already excludes LinkedIn/IG/FB/X direct APIs in v1 — extend that stance to scraping |
| WhatsApp bulk marketing to non-opted-in numbers | WhatsApp is the dominant India business channel | Meta requires pre-approved templates for all business-initiated messages (outside 24h window); marketing templates need explicit opt-in, secondary opt-in after CTWA click; template rejections, quality-rating downgrades (green/yellow/red), tier limits (250 → unlimited users/day), 24-72h sending freezes, permanent number bans | Approved utility/authentication templates first; collect opt-in during any conversation before marketing templates; monitor quality rating; email as the cold channel, WhatsApp for replies/opted-in nurture |
| Autonomous contract signing / auto-escalation to litigation-adjacent commitments | "Fully autonomous agency" is the pitch | Contracts are binding legal documents; LLM-generated legal changes = liability; owner approval before any contract send is the industry trust floor (SPEC-003 FR-082) | Approval gate: draft → owner approve → send. Negotiation agent can draft and discuss but never executes contracts; legal clauses immutable |
| Full autonomy with zero human oversight (the 2024 "AI agency" fantasy) | Vendors sell "replace your SDR entirely" | 2026 market data: fully autonomous AI SDR deployments (Artisan, 11x) largely reverted to hybrid human-AI models (Miniloop, Knock, SaaS Hackers analyses); G2 reviews document quality problems; regulatory winds (EU AI Act transparency) favor auditable human-supervised AI | Design human-in-the-loop from day 1: approvals at contracts/payments/out-of-guardrail, decision log visible, owner can override any agent |
| Voice AI / AI phone dialers (11x Julian-style) | Phone outreach converts well | Consent + call-recording laws (India: TRAI/DPDP considerations), high complexity, provider quality risk. Zero benefit to the India SMB market's WhatsApp-first behavior | Defer to v2+; WhatsApp + email + webchat cover the market |
| Backlink profile analysis / authority scoring at scale (Ahrefs/Semrush-level) | "Complete" SEO picture | Expensive paid APIs ($100-400/mo), low marginal value for SMB qualification; backlinks don't drive the "fixable problem" narrative as well as on-site issues | Defer; on-site audits + Google Maps presence are sufficient for SMB leads |
| Full white-label SaaS resale platform (GHL SaaS mode: client sub-accounts, client billing, rebranded CRM) | Agencies resell software for MRR | Massive platform surface (auth, multi-tenancy, client billing, support) — years of work; PROJECT.md already declares it out of scope (Phase 8.3) | Client report portal (white-label reporting) delivers the client-visible value at 10% of the cost |
| Inbound "speed-to-lead" instant call-back agents for website visitors | Fast inbound response is valuable | Inbound systems need always-on infra + telephony + consent flows; the product's core is outbound + delivery, not inbound lead gen | v2+; start with form → webhook → sales agent email/WhatsApp reply |

## Feature Dependencies

```
[Compliance core: robots.txt + rate limiting + suppression list + audit log]
    └──underlies──> [everything else]

[Lead collection] ──> [Dedup + lineage] ──> [Enrichment + verification] ──> [Scoring] ──> [Qualified queue]
                                                              │
[Website crawler] ──> [Tech stack detection] ──> [Opportunity detection + ROI] ──> [Lead scoring (Automation/AI factors)]
        │                        │                                              │
        └──> [Audit report] ─────┴────> [Proposal generator] <── [Pricing engine] ──> [Negotiation guardrails]
                                                                                         │
[Verification gate] ──> [Outreach sequences] ──> [Reply classification] ──> [Meeting booking]
                                                                                         │
[Proposal] ──> [Contract generator] ──> [OWNER APPROVAL GATE] ──> [E-signature] ──> [Contract executed]
                                                                                         │
[Payments (one-time)] ──> [Recurring billing] ──> [Finance dashboard (MRR/NRR/LTV/CAC)]
[Executed contract] ──> [Project + tasks] ──> [Delivery pipeline] ──> [Maintenance monitoring] ──> [Client reports]
                                                                                                   │
                                                            [Upsell/referral engine] <── [Client health scoring] ─┘
```

### Dependency Notes

- **Verification gate requires enrichment:** verify-before-send is only possible if the enrichment pipeline produced candidate emails with statuses; catch-all/role-based handling must exist before any send. This makes enrichment+verification a hard P1 (it also gates the compliance story).
- **Scoring requires crawler + tech stack detection:** the Automation/AI potential factors (20%+10% of SPEC-002 weights) are computed from crawl output; scoring without crawl is crippled. Crawler is therefore on the critical path to sales.
- **Opportunity detection requires tech stack detection + industry templates:** patterns like "no booking widget" need both the fingerprint data and the per-industry rules/ROI tables. ROI estimates need industry multipliers (already in `backend/config.py` — reusable).
- **Proposal generator requires audit report + pricing engine:** the differentiated proposal format embeds scorecards and monetized opportunities; pricing must be deterministic before negotiation guardrails can be enforced.
- **Negotiation requires pricing engine guardrails:** guardrails (min price, max discount) are outputs of the pricing engine — negotiation without them is just an LLM chatting about money (liability).
- **Contract execution gates project creation:** the delivery pipeline starts from executed contracts + payment schedule; don't build delivery before legal/finance.
- **Finance dashboard requires recurring billing:** MRR/NRR are derived from the billing engine's subscription records; manual entry is a trap (double-entry drift).
- **Client reports require maintenance monitoring:** the report is the monitoring output; monitoring requires deployed client projects (delivery pipeline). Long tail dependency — maintenance only matters after v1 delivery exists.
- **Suppression list is a global dependency:** it must be a single shared store wired into every channel sender (email, WhatsApp, LinkedIn), not per-channel lists — otherwise re-contact violations happen.
- **Audit log underpins approvals and trust:** approval decisions must be logged alongside the agent decisions they override; build the log schema in the foundation phase (SPEC-001), not retrofitted.
- **Anti-feature boundary:** LinkedIn automation and WhatsApp bulk blasts are conflicts with the compliance layer — the compliance core should actively BLOCK these patterns (e.g., reject sends to unverified addresses, refuse logged-in social automation).

## MVP Definition

### Launch With (v1)

A credible, compliance-safe slice of the loop — discovery → outreach → proposal → contract (approval-gated) → payment → basic delivery handoff. Every feature here is table stakes or a cheap differentiator that anchors the product's trust story.

- [ ] Compliance core: robots.txt respect, rate limiting, shared suppression list, audit log (P1 — underpins everything; PROJECT.md compliance sensitivity)
- [ ] Lead collection from 3-5 high-yield compliant sources (Google Places, JustDial, web search, 1-2 directories) with dedup + lineage (P1)
- [ ] Website intelligence: Lighthouse 4-category audit + CWV, broken links, SSL, tech stack detection, SEO checks (P1 — feeds scoring, proposals, opportunity detection)
- [ ] Email discovery + verification with send-time gate (P1 — bounce <2% target; non-negotiable for deliverability and DPDP sourcing story)
- [ ] Weighted lead scoring + tier classification (P1 — drives the qualified queue)
- [ ] Opportunity detection with ROI estimates for 3-5 industries (P1 — the wedge: "you're losing ₹X/month")
- [ ] Outreach sequences (email only) with personalization, follow-ups, unsubscribe, physical address, privacy notice (P1 — WhatsApp/LinkedIn deferred)
- [ ] Reply classification + owner escalation (P1)
- [ ] Proposal generator embedding audit scorecard + opportunities + pricing (P1)
- [ ] Pricing engine with min-price floor + negotiation limits (P1 — deterministic, config-driven)
- [ ] Contract generator from templates + owner approval gate + e-signature (P1)
- [ ] Payment collection (one-time, Stripe/Razorpay) + invoice (P1)
- [ ] Ops dashboard: pipeline kanban, approval center, activity/decision log view (P1)
- [ ] Finance dashboard: MRR/ARR, pipeline value, margin (P1-lite — start with pipeline value; full MRR needs recurring billing)

### Add After Validation (v1.x)

- [ ] WhatsApp channel (approved templates + opt-in flow + quality-rating monitoring) — trigger: email response rate proven; WhatsApp is the India B2B reply channel
- [ ] Recurring billing + maintenance plans — trigger: first clients delivered, MRR demand confirmed
- [ ] Meeting scheduling (Cal.com) + meeting-to-proposal flow — trigger: warm inbound replies
- [ ] Remaining discovery sources (community/job/startup platforms via safe public APIs) — trigger: source registry stable, cost-per-lead tracked
- [ ] Negotiation agent (guardrails + escalation, no contract authority) — trigger: proposal acceptance rate data exists; needs pricing engine in production
- [ ] Automated client reports (white-label) — trigger: first maintenance clients on recurring billing
- [ ] Project/task generation from executed contracts — trigger: contract flow proven; delivery pipeline is its own milestone (SPEC-004)
- [ ] Data freshness re-verification scheduler (30-90 day re-enrichment) — trigger: lead volume warrants it

### Future Consideration (v2+)

- [ ] Client health scoring + upsell/referral engine — needs 6-12 months of maintenance telemetry
- [ ] Voice AI / phone outreach — consent + compliance complexity; India market is WhatsApp-first
- [ ] Backlink analysis — paid APIs; low ROI for SMB qualification
- [ ] Inbound speed-to-lead agents — different market motion
- [ ] Full white-label SaaS resale — explicitly out of scope (PROJECT.md)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Compliance core (robots.txt, rate limits, suppression, audit log) | HIGH | MEDIUM | P1 |
| Lead collection (3-5 sources, dedup, lineage) | HIGH | HIGH | P1 |
| Website intelligence (Lighthouse + tech stack + broken links) | HIGH | MEDIUM | P1 |
| Email verification + send-time gate | HIGH | MEDIUM | P1 |
| Lead scoring (weighted, tiers) | HIGH | MEDIUM | P1 |
| Opportunity detection + ROI (3-5 industries) | HIGH | MEDIUM | P1 |
| Outreach sequences (email, compliant) | HIGH | MEDIUM | P1 |
| Reply classification + escalation | MEDIUM | HIGH | P1 |
| Proposal generator (audit-integrated) | HIGH | MEDIUM | P1 |
| Pricing engine (floors, margins) | HIGH | MEDIUM | P1 |
| Contract generator + approval gate + e-sign | HIGH | MEDIUM | P1 |
| Payment collection + invoices | HIGH | MEDIUM | P1 |
| Ops dashboard (kanban, approvals, decision log) | HIGH | MEDIUM | P1 |
| Finance dashboard (pipeline value first) | MEDIUM | MEDIUM | P1-lite |
| WhatsApp channel | HIGH | HIGH | P2 |
| Recurring billing + maintenance plans | HIGH | MEDIUM | P2 |
| Negotiation agent (guardrails) | MEDIUM | HIGH | P2 |
| Project/task generation | MEDIUM | MEDIUM | P2 |
| Automated client reports | MEDIUM | MEDIUM | P2 |
| Remaining discovery sources | MEDIUM | MEDIUM | P2 |
| Data freshness re-verification scheduler | MEDIUM | LOW | P2 |
| Client health + upsell/referral engine | MEDIUM | HIGH | P3 |
| Voice AI / phone | LOW | HIGH | P3 |
| Backlink analysis | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch (product not credible without it, or blocks other P1s)
- P2: Should have, add when possible (next milestone after core loop works)
- P3: Nice to have / future consideration

## Competitor Feature Analysis

| Feature | GoHighLevel | HubSpot | AI SDR (11x/Artisan/AiSDR) | Clay + Instantly (stack) | Audit tools (PSI/ProspectUp/SEOptimer) | Our Approach |
|---------|-------------|---------|----------------------------|--------------------------|----------------------------------------|--------------|
| Lead database/collection | Paid integrations | Native (prospects) | Built-in (11x 400M+, Artisan DB) | Clay: 50+ sources; Instantly: DB + finder | None | Own 3-5 source collectors + registry (spec'd) — differentiator: no per-seat SaaS cost |
| Email verification | None (external) | External | Partial (11x real-time verify) | Instantly verification; Clay loops | N/A | Native verify-before-send gate with bounce <2% target |
| Website audit | None (funnels only) | None | Deep-research only (no audit) | Claygent web research | PageSpeed free API; ProspectUp full audit | Native Lighthouse + tech stack + opportunity detection |
| Opportunity/ROI detection | None | None | None (ICP fit only) | Partial (signals) | Scores/issues only, no monetized ROI | Industry pattern engine + ROI estimates — unique |
| Lead scoring | Rule-based | Predictive | ICP scoring | Rule-based | N/A | Weighted 7-factor, per-vertical configurable |
| Outreach sequences | Yes (workflows) | Yes | Yes (multi-channel) | Instantly/Smartlead | N/A | Own sequences, email-first |
| Reply handling | Human inbox | Human | AI-classified | Instantly reply agent | N/A | AI classification + owner escalation |
| Negotiation | No | No | No (stop at booking) | No | No | Guardrailed negotiation agent — unique |
| Proposal generation | Templates | Quotes | No | No | White-label audit PDFs | Audit-integrated proposals with ROI — unique |
| Contracts + e-sign | Yes (payments/sign) | Yes (CPQ) | No | No | No | Lawyer templates + approval gate |
| Payments/recurring | Yes (SaaS mode) | Yes (payments) | No | No | No | Stripe/Razorpay + recurring billing |
| MRR/finance dashboard | Basic | Advanced | Pipeline only | No | No | MRR/NRR/LTV/CAC from billing engine |
| Client reports | Yes (white-label) | Yes | No | No | White-label PDFs | Automated maintenance reports (v1.x) |
| Compliance layer | Basic (opt-out) | Basic | Deliverability focus | Verify + suppress | robots.txt-aware crawlers | DPDP-first: consent records, privacy notices, sourcing docs, audit log |
| Human approval gates | Workflow-level | Workflow-level | Some human review | No | N/A | Hard gates: contracts, payments, out-of-guardrail — core trust story |
| Automation platform | Built-in workflows | Built-in | Sequences | Zapier-level | N/A | n8n (self-hosted, free) for client deliveries AND internal plumbing |

## Sources

### AI SDR / market landscape (MEDIUM — multiple secondary sources; market claims vary by vendor)
- Miniloop, "Best AI SDR Tools 2026: Honest Comparison" (2026-04-01) — autonomous AI SDRs reverted to hybrid; pricing tiers
- Instantly, "Artisan vs AI SDR Tools: 2026 Comparison" (2026-08-03) — autonomous vs augmentation spectrum, data provenance
- SaaS Hackers, "Artisan vs AiSDR vs 11x" (2026-06-26) — Clay as enrichment layer under AI SDRs
- 11x.ai, "Artisan vs 11x" (2026-05-02) — 11x feature claims (400M+ contacts, dual agents) — vendor source, treat claims with caution
- zglg.work AI SDR comparison (2026-06-11); Gongchangku 2026 AI SDR comparison (2026-04-21) — Clay pricing/capabilities

### Enrichment, verification, freshness (MEDIUM-HIGH — Apollo official blog + multiple verification vendors)
- Apollo.io, "What SLA Should You Expect From a B2B Data Provider" (2026-04-27) — bounce SLA tiers (<1%/<2%/>5%), spam complaint <0.3%, freshness 30-90 days, catch-all handling, seed-test protocol
- Apollo.io, "What's a Good Email Bounce Rate for Paid Data?" (2026-04-21) — decay management, re-verification cadence
- BillionVerify, "Apollo vs Hunter for Verification" — confidence score vs SMTP verification distinction; find-time vs send-time
- Prospeo, "Lead Data Enrichment 2026" — decay stats; Tomba.io enrichment guide (2026) — 60-90 day re-enrichment cadence
- Lead411, "Email Deliverability Across 10 B2B Data Providers" (2026-04-24) — scraped data worst deliverability

### Website audits / Lighthouse (HIGH — official Google docs for scoring; MEDIUM for vendor feature claims)
- web.dev, "Lighthouse performance scoring" (official) — LH10 weights: FCP 10%, SI 10%, LCP 25%, TBT 30%, CLS 25%
- pagespeed.web.dev — PageSpeed Insights (official)
- Lighthouse score explained (DeployHQ, 2026-07-28) — score bands 90+/50-89/<50; category contents
- ProspectUp, "Website Audits" — letter grades, 30+ tech fingerprints, section breakdown, audit-as-lead-gen
- SE Ranking, "Best Website Audit Tools 2026" (2026-05-07) — health score, error categorization, scheduled crawls
- Insites, "The 10 best website and SEO auditing tools for agencies" (2026-07-16) — agency lead-gen widgets, white-label reports

### Agency CRM / ops dashboard (MEDIUM — official GoHighLevel site + review aggregators)
- gohighlevel.com — official feature/plan pages (CRM, pipelines, unified inbox, workflows, white-label, SaaS mode)
- The Stack Insiders, "GoHighLevel CRM Features & Pipelines (2026)" (2026-07-28) — pipeline/unlimited, feature comparisons
- GHL Experts, "Features of GoHighLevel" — triggers/actions counts, snapshots, sub-accounts

### SaaS finance metrics (MEDIUM — multiple established sources, standard definitions)
- FinOps Masters / SaaS Library / Bricks / ZBuild 2026 guides — MRR/ARR decomposition, NRR, LTV (gross-margin), CAC payback (median 20mo), LTV:CAC 3:1 floor / 3.6:1 median (Benchmarkit 2025), churn benchmarks

### Compliance — cold email law (MEDIUM — legal summaries, general guidance not legal advice)
- Instantly, "GDPR, CAN-SPAM, and B2B email list compliance" (2026-07-15) — CAN-SPAM specifics (10 business days opt-out, physical address, 30-day mechanism)
- InboxKit (2026-03-30), Mailflow Authority (2026-03-31), BounceZero (2026-07-13), Smartlead (2026-06-03) — per-jurisdiction matrix (US opt-out / EU legitimate interest / CA opt-in / AU opt-in), penalty levels
- leadzen.ai, "DPDP Act 2025: What It Means for B2B Prospecting in India" (2026-06-03) — Section 7 numerus clausus, no legitimate-interest equivalent, privacy-notice obligation, processor DPA requirement
- TeamBench, "DPDP Act Marketing Content Compliance" (2026-02-19) — marketing NOT in legitimate-use exemptions; penalties up to INR 250 crore; consent must be unbundled, no dark patterns
- dakshraj.com, "DPDP Act Email Marketing India Compliance" (2026-05-31) — consent records, purchased-list risk, B2B personal-data scope

### Compliance — LinkedIn automation & scraping law (MEDIUM — court records/EFF coverage via multiple secondary sources)
- ConnectSafely, "Is LinkedIn Automation Safe in 2026?" (2026-07-20) — ToS §8.2, enforcement signals, hiQ timeline
- linkedinscraperapi.com, "hiQ v. LinkedIn Scraping Lawsuit: The Ruling Explained" (2026-06-16) — CFAA vs contract/trespass outcomes, Meta v. Bright Data logged-out rule, ProAPIs 2025 fake-account suit
- LegalClarity, "The LinkedIn Scraping Case" (2026-05-20) — consent judgment details ($500K, injunction)
- vLex, X Corp. v. Bright Data (733 F.Supp.3d 832, 2025) — dismissal of scraping claims
- AeroLeads (2026-03-22), LeadsforLinked (2026-05-07) — practical enforcement: account bans, cascading bans

### WhatsApp Business API (MEDIUM-HIGH — Infobip official docs + Meta-documented rules via multiple sources)
- Infobip docs, "Message template compliance" (official) — template approval, statuses, quality ratings
- SuprSend, "WhatsApp Business API Templates Explained" (2026-05-18) — 24h window, categories (auth/utility/marketing), approval flow
- AuditSocials, "WhatsApp Business API Ads Compliance Guide 2026" (2026-04-10) — opt-in requirements, tier limits 250→unlimited, penalties

### Automation platforms (MEDIUM — multiple comparisons)
- Doit.software (2026-06-17), Automation Atlas (2026-07-08), AppStackBuilder (2026-02-12), Digital Applied (2026-06-19) — n8n (self-host, $0, LangChain) vs Make (visual, ~$9-16/mo) vs Zapier (8-9k integrations, priciest at scale)

### Agency client reporting (MEDIUM — vendor sites + comparisons)
- AgencyAnalytics official pages — white-label, scheduled reports, 80+ connectors, AI insights, per-client pricing
- ClientVenue comparison (2025) — DashThis/Whatagraph/Databox feature/pricing landscape
- Nylo, "White-Label Reporting Tool: The 2026 Honest Guide" (2026-05-27) — category analysis: render vs reason vs execute

### Confidence notes
- Lighthouse scoring, WhatsApp template mechanics, and enrichment SLA benchmarks are the strongest-supported claims (official docs / vendor SLAs) → MEDIUM-HIGH
- Market-behavior claims (hybrid > fully autonomous; LinkedIn ban enforcement patterns; DPDP enforcement timeline) are secondary-source consensus → MEDIUM; flagged for validation during compliance phase (legal review recommended)
- Vendor feature claims (11x, GHL, ProspectUp) are from marketing pages → MEDIUM at best; treat quantitative claims (contact counts, response rates) as unverified

---
*Feature research for: AI Agency OS (autonomous AI-powered digital agency platform)*
*Researched: 2026-08-04*

