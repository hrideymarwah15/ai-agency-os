# Phase 2: Discovery - Research

**Researched:** 2026-08-05
**Domain:** Compliant lead collection → normalization → dedup → enrichment → metrics + SSR dashboard
**Confidence:** HIGH (source posture) / MEDIUM (2026 API-terms landscape)

## Summary

The discovery pipeline is implementable with **zero new dependencies** on the Phase 1 stack (FastAPI, SQLAlchemy 2 async + JSONB, httpx, Jinja2 SSR, APScheduler, loguru, pytest). The 2026 source landscape, however, forces a correction to the assumed source list: live verification (robots.txt fetched 2026-08-05; multiple 2026 reports) shows Reddit blocks all crawlers (`User-agent: * / Disallow: /` on www.reddit.com and api.reddit.com) and 403s unauthenticated `.json` requests since May 2026; Yelp's Fusion free tier is now a 30-day evaluation-only trial whose API terms prohibit caching content >24h and AI-model training; Google Maps Platform ToS prohibit caching/storing Content and listings-service use. **The only keyless, terms-permitted live source is the Hacker News Algolia API** (10,000 req/hr/IP, official docs). Recommendation: ship **5 adapters** — `hn` (live), `reddit` (official-API-only, excluded live → the LEAD-04 fixture), `yelp` + `google_places` (key-gated, disabled by default per D-21, terms flagged), and `mock_directory` (mock-only) — each with a MOCK_MODE provider per D-23. In a keyless production run: HN collects, Reddit/Yelp/Google are excluded/disabled with audit events, mock sources unavailable outside MOCK_MODE — which is precisely the "excluded, not scraped" behavior LEAD-04 requires.

**Primary recommendation:** Build the run pipeline as `DiscoveryRun` row + `OutboxEvent` enqueue (the project's declared outbox+worker pattern, REQUIREMENTS.md line 149) consumed by an asyncio worker started in lifespan; adapters implement one `SourceAdapter` ABC over the existing `build_compliant_client()`; dedup = deterministic canonical-key exact match (normalized domain/email/phone/name) + Python-side fuzzy pass (`difflib.SequenceMatcher` ≥ 0.85) — no pg_trgm in this slice (Supabase search_path gotchas, GitHub issue #30503, plus determinism); lineage = `business_source_records` join table (per-source raw payload JSONB + source_item_id); sanitization = stdlib `html.parser`-based extractor with size caps; dashboard = `backend/api/discovery.py` + `discovery.html` following the approvals/audit page pattern.

**One Phase 1 change is required:** the deny-by-default `RobotsPolicy` (Phase 1, D-13) **blocks every documented-API host** — verified: `hn.algolia.com/robots.txt` returns 404 (→ deny-by-default), `api.yelp.com` robots disallows all non-allowlisted agents, `maps.googleapis.com` disallows non-Google bots. Without an explicit API-host exemption, HN (the only live source) can never fetch. Add a minimal `api_hosts` exemption set to `RobotsPolicy`/`build_compliant_client()` (default empty → Phase 1 behavior unchanged, all 86 existing tests keep passing), each exempted host documented in the source's compliance declaration and audited. This is a decision point for the discuss-phase (it extends D-13/D-15), and the recommended default is: exemption ONLY for hosts serving a documented public API consumed via API paths; default deny everywhere else; token bucket still applies.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Source collection (fetch, rate limit, robots) | API / Backend | — | Existing `CompliantHTTPClient` + `DomainTokenBucket` already own this; adapters are thin fetchers over it |
| Source config / enable-disable | API / Backend (env-driven settings) | — | D-21 "unconfigured sources disabled" → `Settings` flags, not a DB table, in this slice |
| Normalization (unified schema, canonical keys) | API / Backend | — | Pure functions (`backend/services/discovery/normalize.py`) — deterministic, unit-testable |
| Dedup (exact + fuzzy) | Database / Storage | API / Backend | Canonical-key lookup in Postgres (indexed); fuzzy pass in Python for determinism; merge transaction in backend |
| Lineage (master + source records) | Database / Storage | — | `business_source_records` join table with `raw_payload` JSONB (D-24) |
| Ingestion sanitization (CMP-06) | API / Backend | — | Sanitize at the ingestion boundary — before anything is persisted or rendered |
| Enrichment (homepage contact scan) | API / Backend | — | Uses the compliant client; robots + per-domain bucket already enforced |
| Run metrics + stats | Database / Storage | API / Backend | Per-run + per-source-stat rows; invariants verified by tests |
| Manual trigger + pipeline page | Frontend Server (SSR) | — | D-17/D-29: Jinja2 SSR via FastAPI routers, zero client JS |
| Daily scheduling | API / Backend | — | D-12: enqueue-only scheduler job → outbox; never long inline jobs |

## Standard Stack

### Core (no new dependencies — reuse Phase 1)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` + `backend/tools/http_client.py` | 0.28.x | All outbound fetches via `CompliantHTTPClient` (robots → bucket → GET) | D-15 single choke point; CMP-01/CMP-02 already shipped and tested |
| `sqlalchemy[asyncio]` + `asyncpg` | 2.0.51+ / 0.31.x | Async ORM; JSONB columns; new tables + Business columns | Existing models/lifecycle; Alembic migrations (FND-03) |
| `jinja2` + FastAPI `Jinja2Templates` | 3.1 / 0.141.x | `discovery.html` SSR page (D-29) | Pattern established in `backend/api/approvals.py` + `approvals.html` |
| `apscheduler` | 3.11.x | Daily discovery enqueue job with heartbeat | D-12 pattern from `backend/services/scheduler.py` |
| `loguru` | 0.7 | Run/source logging with correlation_id | Existing convention (D-18 redaction sink in `main.py`) |
| `pytest` + `pytest-asyncio` | 9.1.1 / 1.4.x | Deterministic tests incl. `httpx.MockTransport` | Established in `tests/test_compliance.py` (zero-network pattern) |
| stdlib `html.parser`, `difflib`, `re`, `urllib` | — | HTML→text, fuzzy match, email/phone/domain extraction, URL validation | D-30: stdlib/BeautifulSoup-class tooling; zero new deps |

### Supporting (parts of the existing stack used conditionally)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `OutboxEvent` model (`backend/database.py:442`) | — | Durable discovery-run enqueue (topic `discovery.run`) | Scheduler + manual trigger both enqueue; worker executes (project-declared outbox pattern) |
| `AuditService` | — | `discovery_run_started/source_excluded/run_finished` etc. with correlation_id | Every run and every exclusion; D-07 threading |
| `Business` model + `Audit`/`OutboxEvent` | — | Master records; future audits; run queue | Extend `Business` with rating/review/enrichment/dedup-key columns |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `HTMLParser` sanitizer | `beautifulsoup4` | bs4 is more forgiving on broken HTML but adds a dep; uv.lock verified to contain no bs4/lxml today [VERIFIED: uv.lock grep]. stdlib is enough for text extraction + mailto/form-URL detection |
| Python `difflib.SequenceMatcher` fuzzy | `pg_trgm` extension | pg_trgm gives indexed fuzzy at scale and exists on Supabase [CITED: supabase docs], but has documented search_path/schema gotchas (GitHub issue #30503) and makes unit tests DB-dependent. Python fuzzy = deterministic, migration-free; pg_trgm documented as the 100k-row scale-up |
| Outbox worker (`OutboxEvent` + asyncio task) | Direct `asyncio.create_task` from the trigger endpoint | Outbox survives restarts and matches the project's declared "Postgres outbox + asyncio worker" architecture (REQUIREMENTS.md); direct tasks lose queued runs on crash |
| Env-driven source registry (`Settings` flags) | `discovery_sources` DB table (SPEC §8.1) | DB table is spec-aligned but adds admin UI surface this slice doesn't need; env flags are testable via `monkeypatch` and match D-21 "unconfigured sources are disabled" |

**Version verification** (2026-08-05, from `pyproject.toml` + `uv.lock` — the project's locked versions, not registry defaults): fastapi 0.141.x, sqlalchemy 2.0.51+, httpx 0.28.x, apscheduler 3.11.x, jinja2 3.1, pytest 9.1.1, pytest-asyncio 1.4.x. No version changes proposed.

## Package Legitimacy Audit

> Gate run 2026-08-05. **This phase proposes ZERO new external packages** — every capability is built on the existing locked stack + stdlib (D-30's "zero new deps" preference).

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| (none new) | — | — | Approved — no new installs; `uv lock` untouched |

Existing-dependency scan: `slopcheck scan .` → 26/26 `[OK]` on the current lock (httpx, fastapi, sqlalchemy, asyncpg, apscheduler, jinja2, pytest, …). **Packages removed due to slopcheck [SLOP] verdict:** none. **Packages flagged [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
                    ┌──────────────────────────────────────────────────────────────┐
                    │                      OWNER (browser)                          │
                    └───────┬──────────────────────────────────┬───────────────────┘
                            │ GET /discovery (Jinja2 SSR)      │ POST /discovery/run
                            ▼                                  ▼
                    ┌───────────────┐                  ┌──────────────────┐
                    │ /discovery    │                  │ /discovery/run   │  (owner-guarded,
                    │ page: runs +  │                  │ create DiscoveryRun│  _check_origin)
                    │ source stats  │                  │ + OutboxEvent    │
                    │ + lead counts │                  └────────┬─────────┘
                    └───────┬───────┘                           │
                            │ read runs/businesses              ▼
                    ┌───────▼──────────────────────────────────────────────────────┐
                    │                    PostgreSQL (asyncpg)                      │
                    │  discovery_runs ──< discovery_run_source_stats                │
                    │  businesses <── business_source_records (lineage + raw JSONB) │
                    │  outbox_events (discovery.run)   audit_logs (correlation_id)  │
                    └───────▲───────────────────────────────────────┬──────────────┘
                            │ poll PENDING                          │ upsert status/stats
                    ┌───────┴───────────────────────────────────────▼──────────────┐
                    │          DISCOVERY WORKER (asyncio task, lifespan)           │
                    │  for each enabled source (registry, MOCK_MODE swaps impl):   │
                    │   adapter.fetch_candidates(ctx) → SourceCandidate stream     │
                    └───────┬──────────────────────────────────────────────────────┘
                            │ build_compliant_client(api_hosts={hn.algolia.com, …})
                            ▼
              ┌───────────────────────────────┐
              │  COMPLIANT HTTP DOOR (D-15)   │  robots check (deny-by-default,
              │  api_hosts → skip robots      │  EXCEPT api_hosts) → per-domain
              │  (API ToS governs, audited)   │  token bucket + jitter → httpx GET
              └───────────────────────────────┘
                            │ raw payloads (HTML from HN comments/homepages, JSON)
                            ▼
              normalize (pure fns) → sanitize (CMP-06: HTML→text, caps, inert tokens)
              → dedup (canonical key idx → fuzzy difflib) → merge master + lineage row
              → enrich (homepage scan: email/phone/form URL, fill-if-missing FR-062)
              → per-source stats (parsed_ok/rejected buckets/new/merged/requests)
              → audit (run-level, correlation_id) → run status COMPLETED/PARTIAL/FAILED
```

### Recommended Project Structure

```
backend/
├── database.py                     # + DiscoveryRun, DiscoveryRunSourceStat, BusinessSourceRecord models
│                                   # + Business columns: rating, review_count, last_enriched_at,
│                                   #   enrichment_version, dedup_key_{name,domain,email,phone}
├── config.py                       # + source enable flags + caps (SOURCE_HN_ENABLED etc., max items, caps)
├── tools/http_client.py            # + api_hosts exemption (RobotsPolicy bypass set) + fetch(headers=)
├── services/compliance/robots.py   # + api_hosts param (default ∅ → unchanged)
├── services/discovery/
│   ├── __init__.py
│   ├── registry.py                 # source_id → adapter class + compliance posture + enabled flag
│   ├── base.py                     # SourceAdapter ABC, RunContext, SourceCandidate, ParseError, RejectReason
│   ├── sources/
│   │   ├── hn.py                   # HN Algolia "Who is hiring" adapter + MockHN adapter
│   │   ├── reddit.py               # official-API-only adapter; live-excluded; Mock adapter
│   │   ├── yelp.py                 # Fusion adapter, key-gated disabled; Mock adapter
│   │   ├── google_places.py        # Places adapter, key-gated disabled; Mock adapter
│   │   └── mock_directory.py       # mock-only source for demos/tests
│   ├── normalize.py                # pure: normalize_domain/phone/email/name + HN→unified mapping
│   ├── dedup.py                    # canonical keys + difflib fuzzy + merge-if-missing (FR-062)
│   ├── sanitize.py                 # stdlib HTMLParser → text; caps; control-token guard (CMP-06)
│   ├── enricher.py                 # homepage scan: email/phone/form URL via compliant client
│   ├── runner.py                   # execute_run(): collect→normalize→sanitize→dedup→merge→stats
│   └── worker.py                   # outbox-polling asyncio task (started in lifespan)
├── services/scheduler.py           # + _discovery_daily_job (enqueue-only, heartbeat)
├── api/discovery.py                # GET /discovery (page) + POST /discovery/run (trigger)
├── templates/discovery.html        # extends base.html; runs table + per-source stats
├── templates/base.html             # + "Discovery" nav link (active_page)
└── main.py                         # include discovery router; start worker task in lifespan
tests/
├── fixtures/injections.json        # adversarial payloads (CMP-06 fixtures)
├── fixtures/hn_whoishiring_sample.json
└── test_discovery_*.py             # normalize/dedup/sanitize/runner/api/worker (see Validation Architecture)
```

### Pattern 1: Source Adapter Interface

**What:** One ABC; each source declares its compliance posture (`api_hosts` for robots exemption, `enabled` gating, rate-limit notes); adapters yield `SourceCandidate` streams; parse failures become `ParseError` with a bounded reason bucket (LEAD-05 rejection metrics). Mirrors the `backend/services/` service style and `backend/tools/http_client.py` shape.

**When to use:** Every external source, live and mock. MOCK_MODE (D-20/D-23) swaps registry entries, never adapter internals.

```python
# backend/services/discovery/base.py (interface sketch)
class RejectReason(str, enum.Enum):  # bounded buckets for LEAD-05 metrics
    MISSING_NAME = "missing_name"
    MISSING_WEBSITE = "missing_website"
    MALFORMED = "malformed"
    TOO_SHORT = "too_short"
    BLOCKED = "blocked"          # robots denied / HTTP 403 / excluded platform
    DISABLED = "disabled"        # source not configured (D-21)

@dataclass
class RunContext:
    run_id: UUID
    correlation_id: str
    client: CompliantHTTPClient      # the D-15 door, already api_hosts-aware
    session: AsyncSession
    stat: SourceStatCollector         # per-source counters + rejection buckets

@dataclass
class SourceCandidate:
    source_item_id: str               # idempotency key: unique per source item
    raw: dict[str, Any]               # sanitized+size-capped raw payload (lineage, D-24)
    text: str                         # sanitized text (CMP-06: inert, data-only)
    normalized: dict[str, Any]        # unified schema subset (SPEC-002 §8.2)

class SourceAdapter(ABC):
    source_id: ClassVar[str]
    display_name: ClassVar[str]
    api_hosts: ClassVar[frozenset[str]] = frozenset()   # robots-exempt API hosts
    requires_keys: ClassVar[bool] = False               # Yelp/Google: key-gated
    @abstractmethod
    async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]: ...
    # raise ParseError(RejectReason) per item on failure; never swallow into candidates
```

### Pattern 2: Outbox Enqueue + Worker (D-12 compliant)

**What:** Manual trigger and the daily scheduler job only CREATE the run row + an `OutboxEvent(topic="discovery.run", payload={"run_id": …})`. A single asyncio worker (started in `lifespan`, tracked on `app.state`) polls PENDING outbox events, executes runs serially, and marks them DONE/FAILED. Heartbeat/staleness stays with the scheduler (01-04 pattern).

**Why:** REQUIREMENTS.md line 149 chose "Postgres outbox + asyncio worker" over Celery/Temporal; D-12 forbids long inline jobs (a multi-source run with per-domain buckets can take minutes); outbox survives restarts.

```python
# scheduler job (enqueue-only — exact D-12 shape)
async def _discovery_daily_job() -> None:
    async with database.async_session_maker() as session:
        run = DiscoveryRun(trigger_source="SCHEDULER", status=RunStatus.RUNNING,
                           correlation_id=str(uuid4()))
        session.add(run)
        await session.flush()
        session.add(OutboxEvent(topic="discovery.run",
                                payload={"run_id": str(run.id), "correlation_id": run.correlation_id}))
        await session.commit()
```

### Pattern 3: Dedup — Canonical Keys + Python Fuzzy (deterministic, testable)

**What:** Per candidate: (1) exact lookup on indexed canonical keys (`dedup_key_domain`, `dedup_key_email`, `dedup_key_phone`, `dedup_key_name`); (2) fuzzy pass — same normalized domain (strongest signal) OR `difflib.SequenceMatcher(None, name_a, name_b).ratio() >= 0.85` AND phone/domain agreement. New candidates become master records; hits attach a `BusinessSourceRecord` lineage row and merge fill-if-missing fields (FR-062). Dedup rate = `merged / (new + merged)` reported per run (D-25).

**Why:** deterministic (no DB extension, no search_path issues — Supabase pg_trgm gotcha GitHub #30503 [CITED]), trivially unit-tested with a fixture corpus, and exact keys index cleanly on the existing Postgres.

```python
# backend/services/discovery/normalize.py (pure, unit-testable)
_LEGAL_SUFFIXES = ("llc", "inc", "ltd", "pvt", "private limited", "limited", "co", "corp", "gmbh")

def normalize_domain(website: str | None) -> str | None:
    if not website: return None
    host = urlparse(website if "://" in website else f"https://{website}").hostname
    if not host: return None
    host = host.lower().removesuffix("www.").strip(".")
    return host or None          # NOTE: no public-suffix handling in MVP — see Pitfall 2

def normalize_phone(phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    return digits or None        # best-effort; country-prefix normalization is a later refinement

def normalize_email(email: str | None) -> str | None:
    return (email or "").strip().lower() or None

def normalize_name(name: str | None) -> str | None:
    if not name: return None
    s = " ".join(name.lower().split())                      # collapse whitespace
    s = re.sub(r"[^a-z0-9 ]", " ", s)                       # punctuation → space
    words = [w for w in s.split() if w not in _LEGAL_SUFFIXES]
    return " ".join(words) or None
```

### Pattern 4: Ingestion Sanitization (CMP-06)

**What:** At ingestion, before persistence: strip HTML to text (stdlib `HTMLParser` subclass dropping `script`/`style`/`noscript`, collecting data), `html.unescape`, collapse whitespace, drop control characters, cap raw bytes (512 KB) and text length (20 KB). Stored sanitized text is **data only** — this slice contains no prompt builder at all; the invariant "scraped content never reaches instruction context" is enforced by (a) sanitize-at-ingestion, (b) Jinja autoescape on every render, (c) a `strip_control_tokens()` helper (strips `<|endoftext|>`-style sequences) that future LLM-facing phases MUST route prompt input through — verified by adversarial fixtures (D-27, SPEC-002 §15).

```python
# backend/services/discovery/sanitize.py (stdlib only)
class _TextExtractor(HTMLParser):
    """Collect text; drop script/style/noscript blocks entirely."""
    _SKIP = frozenset({"script", "style", "noscript"})
    def __init__(self): super().__init__(convert_charrefs=True); self.parts: list[str] = []; self._skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP: self._skip += 1
    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip: self._skip -= 1
    def handle_data(self, data):
        if not self._skip: self.parts.append(data)

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TOKENS = ("<|endoftext|>", "<|im_start|>", "<|im_end|>", "|>|endoftext|<|")

def strip_html_to_text(raw: str, *, max_bytes: int = 512_000, max_text: int = 20_000) -> str:
    if len(raw.encode()) > max_bytes: raw = raw[:max_bytes]   # hard cap at read
    parser = _TextExtractor()
    try: parser.feed(raw)
    except (UnicodeDecodeError, HTMLParseError): pass          # never raise on hostile input
    text = " ".join(_CTRL_RE.sub("", " ".join(parser.parts).split()))
    return text[:max_text]

def strip_control_tokens(text: str) -> str:
    """Prompt-boundary guard: LLM-facing phases MUST route scraped content through this."""
    return re.sub("|".join(map(re.escape, _TOKENS)), "", text)
```

### Pattern 5: API-Host Robots Exemption (minimal Phase 1 delta — see Open Question Q1)

**What:** `RobotsPolicy` gains an `api_hosts: frozenset[str]` set; `can_fetch()` returns True for those hosts (documented API terms govern; token bucket still applies) and audits one `api_source_exempt` event per host at first use. Default `∅` → all 86 Phase 1 tests unchanged.

```python
# backend/services/compliance/robots.py (delta)
def __init__(self, client, *, user_agent: str, ttl_seconds: int,
             session: AsyncSession | None = None, api_hosts: frozenset[str] = frozenset()) -> None:
    self._api_hosts = api_hosts
    ...
async def can_fetch(self, url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host in self._api_hosts:
        await self._audit_api_exempt_once(host)     # one audit per host per process
        return True
    ...  # existing deny-by-default path untouched
```

### Anti-Patterns to Avoid

- **Per-candidate audit rows:** one audit per candidate floods `audit_logs`; audit at run/source granularity and keep per-candidate detail in `business_source_records` + stat buckets.
- **Storing raw HTML in JSONB:** always store the sanitized text (CMP-06); raw HTML in templates = stored XSS.
- **Robots bypass by retry-on-403:** a `RobotsDeniedError`/403 must EXCLUDE the source with an audit event (LEAD-04) — never retry harder, never use alternate domains/IPs to "scrape around".
- **LLM in the collection loop:** normalization/dedup/sanitization are pure code — no LLM calls (costs, non-determinism, injection surface).
- **Fuzzy-only dedup without exact keys:** fuzzy-only produces false merges; exact canonical keys are the backbone (see Pitfall 2).
- **Enrichment URLs from content without validation:** homepage scans must reject `http://localhost`, private/loopback/link-local IPs, and non-80/443 ports (SSRF — see Security Domain).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML→text extraction | Regex tag-stripping | stdlib `html.parser.HTMLParser` subclass | Regex breaks on malformed HTML, comments, CDATA; parser handles nesting and is already in stdlib |
| Robots.txt policy | Custom robots parser | Existing `RobotsPolicy` (D-13, `urllib.robotparser`) | Shipped + tested in Phase 1 (T-05-xx); deny-by-default is locked |
| Per-domain rate limiting | Custom limiter | Existing `DomainTokenBucket` (CMP-02) | Shipped + tested; one bucket keyed per domain = per-source isolation for API hosts |
| Durable run queue | Redis/Celery/Temporal | Existing `OutboxEvent` model + asyncio worker | Project-declared pattern (REQUIREMENTS.md line 149); no new infra |
| Audit trail | Direct table writes | `AuditService.record` (D-07) | Append-only immutability is DB-enforced; single write path |
| Fuzzy string matching | Hand-rolled edit distance | `difflib.SequenceMatcher` (stdlib) | Deterministic, zero-dep; pg_trgm is the documented scale-up, not the MVP |
| Session auth for the trigger | Custom tokens | `get_current_owner` + `_check_origin` | D-16 + T-03-03 pattern from approvals.py |

**Key insight:** Phase 1 deliberately built the compliance door (robots + bucket) and the durable queue (outbox); this phase's complexity is in *plumbing*, not new infrastructure. Every "infrastructure" problem here already has a shipped answer — the only genuinely new machinery is the adapter/normalize/dedup/sanitize logic, all pure Python, all deterministically testable.

## Common Pitfalls

### Pitfall 1: Deny-by-default robots blocks legitimate API hosts
**What goes wrong:** The Phase 1 client refuses `hn.algolia.com` (robots.txt 404 → deny) and `api.yelp.com` (disallow-all) — the run silently finds zero sources. **Root cause:** CMP-01's safe default was designed for web crawling; documented API hosts are governed by API terms, not robots. **How to avoid:** `api_hosts` exemption set per source + audit (Pattern 5); only API hosts, only with a compliance declaration. **Warning signs:** `robots_denied_by_default` audit rows for api.* hosts; source stats all `BLOCKED`.

### Pitfall 2: Dedup false positives/negatives
**What goes wrong:** Same business stored twice (missed merge — e.g., "Acme Tech" vs "Acme Tech Pvt. Ltd." with different domains) or two businesses merged (e.g., "Delhi Dental Clinic" chains). **Root cause:** bare string equality on raw fields; no suffix stripping; phone formats differ across sources (`+91-11-2345 6789` vs `01123456789`). **How to avoid:** canonical keys with suffix stripping and digits-only phones; domain key = strongest signal but treat subdomains/`www.` correctly; fuzzy only as a *secondary* pass with a second corroborating key (domain OR phone). Do NOT implement public-suffix logic in the MVP — flag `*.github.io`-style collisions as known-acceptable false negatives (see Assumptions A4). **Warning signs:** dedup-rate metric >95% (suspicious over-merge) or <40% (under-merge); dashboard shows obvious near-duplicate rows.

### Pitfall 3: Injection edge cases (CMP-06)
**What goes wrong:** A source comment containing `{{7*7}}` or `<script>` survives into the dashboard and renders; or a `<|endoftext|>` token later lands in a prompt. **Root cause:** storing raw HTML; rendering without escaping; no boundary helper for future prompt builders. **How to avoid:** sanitize at ingestion (HTMLParser + caps + control chars); Jinja2 autoescape is on by default for `.html` templates [VERIFIED: FastAPI `Jinja2Templates` behavior] — never use `|safe` on scraped fields; fixture-driven tests assert inertness (see Validation Architecture). **Warning signs:** any `|safe` filter on scraped content in templates; raw HTML stored in `raw_payload`.

### Pitfall 4: Rate-limit / 429 handling
**What goes wrong:** HN Algolia (10,000 req/hr/IP) or future sources 429 mid-run; run marked FAILED instead of PARTIAL with per-source stats. **Root cause:** treating source errors as run errors; no 429-aware handling. **How to avoid:** per-source stats with status OK/EXCLUDED/BLOCKED/ERROR/EMPTY (run = PARTIAL when ≥1 source failed, COMPLETED when all enabled sources attempted); treat 429 as BLOCKED-with-audit and stop that source for the run; keep `max_instances=1` semantics via worker serialization. **Warning signs:** `requests_made` counter plateau; run duration ≫ expected from bucket math.

### Pitfall 5: Run metadata vs candidate data confusion
**What goes wrong:** Metrics drift from truth (stats say 10 parsed but 8 rows exist) because stats are computed outside the same transaction as inserts. **Root cause:** updating `discovery_runs` totals in a second transaction. **How to avoid:** compute and write stats in the SAME transaction as candidate inserts; test invariants `candidates_found == parsed_ok + rejected` and `new + merged == parsed_ok` per source (see Validation Architecture). **Warning signs:** any test asserting stats requires `sleep`/eventual consistency.

### Pitfall 6: Enrichment homepage scans as an SSRF/abuse vector
**What goes wrong:** A source item contains `website: http://169.254.169.254/` or `http://localhost:5432`; the enricher fetches it (metadata service / internal DB). **Root cause:** trusting source-provided URLs. **How to avoid:** URL validation before ANY fetch: scheme ∈ {http, https}; hostname resolves to public IP only (reject loopback/private/link-local/ULA via `ipaddress`); port 80/443 only; cap redirects (httpx default 20 → set ≤ 3). **Warning signs:** enricher requests to non-public IPs logged; enrichment of obviously internal-looking hostnames.

## Code Examples

### HN "Who is hiring" collection (live source — official API shape)
```python
# backend/services/discovery/sources/hn.py — endpoints per hn.algolia.com/api [VERIFIED: official docs]
SEARCH = "https://hn.algolia.com/api/v1/search_by_date?tags=story&query=Ask%20HN%20Who%20is%20hiring&hitsPerPage=5"
ITEM   = "https://hn.algolia.com/api/v1/items/{object_id}"

async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]:
    # 1) latest "Who is hiring?" thread
    resp = await ctx.client.fetch(SEARCH)                     # robots-exempt api host + bucket
    thread = resp.json()["hits"][0]                           # newest matching story
    # 2) its top-level comments = job posts (Company | Role | Location | URL, free-form)
    resp = await ctx.client.fetch(ITEM.format(object_id=thread["objectID"]))
    for child in resp.json().get("children", []):
        text = sanitize.strip_html_to_text(child.get("text") or "")
        if len(text.split()) < 4:                             # empty/deleted comments
            raise ParseError(RejectReason.TOO_SHORT, item_id=child["id"])
        yield SourceCandidate(
            source_item_id=f"hn:{child['id']}",
            raw={"hn_id": child["id"], "thread_id": thread["objectID"], "author": child.get("author")},
            text=text,
            normalized=normalize_hn_job_post(text, child),    # name/website/industry/location heuristics
        )
```

### Adapter test (zero-network, established pattern — tests/test_compliance.py style)
```python
# tests/test_discovery_sources_hn.py
def _hn_handler(thread_body: str):
    import json, httpx
    def handler(request: httpx.Request) -> httpx.Response:
        if "/items/" in request.url.path:
            return httpx.Response(200, json={"children": json.loads(thread_body)})
        return httpx.Response(200, json={"hits": [{"objectID": "9999", "title": "Ask HN: Who is hiring?"}]})
    return handler

async def test_hn_adapter_yields_candidates(mock_transport):
    from backend.tools.http_client import build_compliant_client
    client = build_compliant_client(mock_transport(_hn_handler(THREAD_FIXTURE)),
                                    api_hosts=frozenset({"hn.algolia.com"}))
    ctx = RunContext(run_id=uuid4(), correlation_id="corr", client=client,
                     session=test_session, stat=SourceStatCollector("hn"))
    items = [c async for c in HNAlgoliaSource().fetch_candidates(ctx)]
    assert len(items) == 2 and items[0].normalized["website"].endswith("example.com")
```

### Dedup merge (fill-if-missing enrichment — FR-062)
```python
# backend/services/discovery/dedup.py
_MASTER_FIELDS = ("name", "industry", "website_url", "email", "phone", "location",
                  "employee_count", "rating", "review_count", "tech_stack")
async def merge_into_master(session: AsyncSession, master: Business,
                            candidate: SourceCandidate, *, run_id: UUID) -> None:
    for field in _MASTER_FIELDS:                       # incremental enrichment: only missing fields
        if getattr(master, field) in (None, [], {}):
            setattr(master, field, candidate.normalized.get(field))
    master.raw_data = master.raw_data or {}            # keep existing; never overwrite lineage
    session.add(BusinessSourceRecord(
        business_id=master.id, run_id=run_id, source_id=candidate.source_id,
        source_item_id=candidate.source_item_id, raw_payload=candidate.raw,
        sanitized_text=candidate.text, status="MERGED"))
```

### Run trigger endpoint (owner-guarded — approvals.py pattern)
```python
# backend/api/discovery.py
@router.post("/run")
async def trigger_discovery(request: Request, _owner: str = Depends(get_current_owner),
                            session: AsyncSession = Depends(get_db)) -> Response:
    _check_origin(request)                              # T-03-03 pattern
    run = DiscoveryRun(trigger_source="MANUAL", status=RunStatus.RUNNING,
                       correlation_id=str(uuid4()))
    session.add(run); await session.flush()
    session.add(OutboxEvent(topic="discovery.run", payload={"run_id": str(run.id)}))
    await AuditService.record(session, actor="owner", action="discovery_triggered",
                              entity_type="discovery_run", entity_id=str(run.id),
                              payload={"trigger_source": "MANUAL"}, correlation_id=run.correlation_id)
    await session.commit()
    response = RedirectResponse(url="/discovery", status_code=302)
    set_flash(response, "Discovery run queued.", kind="success")
    return response
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Reddit free `.json` endpoint (append `.json` to any URL, keyless) | Blocked: 403 on unauthenticated requests at scale; robots.txt `Disallow: /` for all | Late May 2026 [CITED: prowlo.com 2026-07-22, redditapis.com; VERIFIED: live robots.txt fetch] | Reddit cannot be a live keyless source; becomes the LEAD-04 exclusion fixture; official Data API (OAuth app, free tier 100 req/min, commercial-restricted) is the only live path — backlog |
| Yelp Fusion free tier 5,000 calls/day | Free tier is now a 30-day evaluation-only trial; production = $229+/mo plans; API terms prohibit >24h content caching and AI training | 2025–2026 pricing change [CITED: docs.developer.yelp.com places-faq + api_terms 20250113] | Yelp cannot persist master-record data; adapter key-gated disabled + mock only, terms documented (D-21 "unconfigured sources are disabled") |
| Google Places as low-key source | Maps Platform ToS prohibit caching/storing Content outside the Service and listings-service use of business-listings Content [CITED: cloud.google.com/maps-platform/terms] | Long-standing ToS | Google Places adapter optional + disabled; would need compliance review + no persistent raw payload (conflicts with D-24 lineage) |
| Robots.txt consulted for every fetch incl. API hosts | API-host exemption set for documented public APIs (API ToS + rate limits govern instead) | This phase (Q1) | Required or HN can never fetch under deny-by-default; default deny preserved everywhere else |

**Deprecated/outdated:**
- Reddit unauthenticated `.json` scraping: blocked/403 since May 2026; never build on it.
- Yelp "free tier": trial-only for evaluation since 2025/2026 — do not plan production collection on it.
- `FID` (First Input Delay): superseded by INP — relevant only to Phase 02.1 (already locked in ROADMAP).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HN Algolia remains free/keyless/10k-req-hr through this phase | Sources | HIGH if changed — would leave zero live sources; mitigations: source disabled-flag design, mock coverage |
| A2 | The `api_hosts` robots exemption is acceptable to the user as an extension of D-13/D-15 (Open Question Q1) | Architecture Patterns | HIGH — if rejected, no live source can fetch; discuss-phase must confirm |
| A3 | Yelp Fusion / Google Places are acceptable as disabled-by-default adapters with mock providers rather than removed entirely | Sources | LOW — they satisfy "3-5 adapters + unconfigured = disabled"; if user prefers removal, count drops to 3 adapters |
| A4 | Public-suffix handling (e.g., `blogspot.com` vs `example.blogspot.com`) is out of scope; domain key uses full hostname minus `www.` | Dedup | MEDIUM — false negatives on shared-hosting domains; accepted for MVP, documented |
| A5 | Phone dedup uses digits-only exact match (no country-code folding) | Dedup | MEDIUM — cross-source phone merges may miss `+91` vs `011` variants; best-effort per D-25 wording |
| A6 | Enrichment in this slice = homepage contact scan (email/phone/form URL) + source-provided fields only; tech-stack *detection* stays in 02.1 | Enrichment | LOW — scope creep risk if plan misreads LEAD-02; keep tech_stack from source signals only |
| A7 | `difflib.SequenceMatcher` ≥ 0.85 threshold is a reasonable MVP default | Dedup | MEDIUM — threshold tuning may be needed with real corpus; keep it a module constant, not magic in code |
| A8 | `httpx.Response.json()` on HN/Yelp payloads is safe (JSON content-type) without extra parsing libs | Sources | LOW — standard; orjson not needed for MVP volumes |

## Open Questions

1. **API-host robots exemption (Q1 — must be confirmed in discuss-phase):** the Phase 1 deny-by-default policy blocks hn.algolia.com (404 robots) and api.yelp.com (disallow-all). We know: exemption set default-empty keeps Phase 1 behavior; token bucket still applies. What's unclear: whether the user accepts extending D-13/D-15 for documented API hosts. Recommendation: accept with the strict rule (API paths only + audit + terms URL per source); reject → HN/Yelp adapters become excluded and the slice ships mock-only live, failing LEAD-01's "collects from sources" intent.
2. **Reddit adapter posture:** implement as live-excluded fixture (recommended — satisfies LEAD-04 with real evidence) vs drop entirely. If dropped, the exclusion fixture must be a mock (weakens the demo). Recommendation: keep as excluded-live adapter.
3. **Yelp/Google key-gated adapters:** implement adapter + mock now (recommended) vs defer entirely to backlog. Recommendation: implement now — they're cheap with mocks and satisfy the "3-5 sources" contract.
4. **Enrichment homepage scan scope:** confirm email/phone/form-URL-only (recommended; tech detection → 02.1). Risk: plan creep into AUDT territory.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL (local test DB) | All DB tests, `migrated_db` fixture | ✓ | accepting on /tmp:5432 (`pg_isready` OK) | docker-compose in repo |
| Python venv (`.venv`) | Everything | ✓ | 3.12.12 | `uv sync` |
| pytest / pytest-asyncio | Validation | ✓ | 9.1.1 / auto mode | — |
| Alembic | Migrations | ✓ | in venv | — |
| hn.algolia.com | Live HN adapter (network test only) | ✓ | reachable (curl 200) | Mock transport in tests; no network in CI |
| Network access in CI | Live source smoke tests | ✗ (assume) | — | All tests use `httpx.MockTransport` (test_compliance.py pattern); live fetch is a manual/demo path |
| MOCK_MODE | Deterministic runs + demo | ✓ (config flag D-20) | — | — |

**Missing dependencies with no fallback:** none (zero new packages/tools required).

## Validation Architecture

> `workflow.nyquist_validation: true` in `.planning/config.json` — section required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.x (`asyncio_mode = "auto"`, function loop scope) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (exists) |
| Quick run command | `uv run pytest tests/test_discovery_dedup.py tests/test_discovery_normalize.py tests/test_discovery_sanitize.py -x -q` |
| Full suite command | `uv run pytest -q` (existing 86 + new; CI gates: ruff → black → mypy → pytest) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LEAD-01 | Registry enables/disables 5 adapters; per-source rate limiting; unconfigured sources disabled | unit + integration | `tests/test_discovery_registry.py` | ❌ Wave 0 |
| LEAD-01/LEAD-04 | Blocked source (Reddit fixture: robots deny / 403) is EXCLUDED with audit event, never fetched | integration (MockTransport + migrated_db) | `tests/test_discovery_exclusion.py` | ❌ Wave 0 |
| LEAD-02 | Normalization maps each adapter payload to unified fields (name/industry/website/email/phone/location/employees/reviews/ratings/tech_stack) | unit | `tests/test_discovery_normalize.py` | ❌ Wave 0 |
| LEAD-02 | Incremental enrichment fills only missing fields; homepage scan extracts email/phone/form URL | unit + integration | `tests/test_discovery_enricher.py` | ❌ Wave 0 |
| LEAD-03 | Same business from 2 adapters → ONE master, lineage shows both `source_ids`; dedup rate metric | integration (deterministic fixtures) | `tests/test_discovery_dedup.py` | ❌ Wave 0 |
| LEAD-05 | Manual trigger creates run + outbox event; per-run invariants: `found == parsed + rejected`, `new + merged == parsed` per source | integration + API | `tests/test_discovery_run.py`, `tests/test_discovery_api.py` | ❌ Wave 0 |
| LEAD-05 | Scheduler daily job enqueues (short, heartbeat), worker executes runs, PARTIAL on partial source failure | integration | `tests/test_discovery_worker.py` | ❌ Wave 0 |
| DASH-02 | `/discovery` page renders recent runs, per-source stats, lead counts (owner-guarded; structured-only view model) | integration (TestClient + session cookie) | `tests/test_discovery_api.py` | ❌ Wave 0 |
| CMP-06 | Adversarial fixtures (injections.json) inert: stored as data, rendered escaped, control tokens stripped by `strip_control_tokens` | unit + integration | `tests/test_discovery_sanitize.py` | ❌ Wave 0 |
| CMP-06 | Enrichment URL validation rejects localhost/private-IP targets (SSRF) | unit | `tests/test_discovery_sanitize.py` or `test_discovery_enricher.py` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_discovery_*.py -x -q`
- **Per wave merge:** `uv run pytest -q` (full suite, CI-equivalent)
- **Phase gate:** full suite green + `ruff check .` + `black --check .` + `mypy backend/` before `/gsd-verify-work` (CI mirrors this, `.github/workflows/ci.yml`)

### Wave 0 Gaps
- [ ] `tests/conftest.py` — add `discovery_db` fixture (clean discovery tables, mirroring `compliance_db`) and `injections.json`/`hn_whoishiring_sample.json` fixtures
- [ ] `tests/test_discovery_sanitize.py` — CMP-06 adversarial fixtures (FIRST — the phase's security gate)
- [ ] `tests/test_discovery_normalize.py`, `tests/test_discovery_dedup.py` — pure-logic tests (no DB)
- [ ] `tests/test_discovery_run.py`, `tests/test_discovery_worker.py`, `tests/test_discovery_api.py`, `tests/test_discovery_exclusion.py`, `tests/test_discovery_registry.py` — integration (migrated_db)
- [ ] No new framework install needed — pytest stack already green (86 tests)

## Security Domain

> `security_enforcement: true` (absent key = enabled), ASVS level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing `get_current_owner` session dependency on all discovery routes (D-16 pattern) |
| V3 Session Management | yes | Existing signed cookie session (itsdangerous), SameSite=Lax; `_check_origin` on mutating POSTs (T-03-03 pattern) |
| V4 Access Control | yes | Owner-only trigger + page; worker runs as `system` actor |
| V5 Input Validation | yes | Pydantic/sanitizer: `strip_html_to_text` + field caps + URL validation (scheme/port/IP) before enrichment fetch |
| V6 Cryptography | no | No new crypto in this slice (sessions already signed) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via scraped content (CMP-06) | Tampering / Spoofing | Sanitize at ingestion (HTMLParser + caps + control-char strip); scraped content stored as data only; `strip_control_tokens()` boundary helper for any future LLM prompt path; adversarial fixtures assert inertness |
| Stored XSS via source content in dashboard | Tampering | Never `|safe` scraped fields; Jinja2 autoescape (default for `.html` in FastAPI `Jinja2Templates`); structured-only view model (T-03-01 pattern from approvals.py) |
| SSRF via enriched website URLs | Spoofing | Enrichment fetches validate: scheme http/https only, public IP only (reject loopback/private/link-local/ULA via `ipaddress`), ports 80/443, redirect cap ≤ 3 |
| SQL injection via search/dedup input | Tampering | SQLAlchemy ORM parameterized queries only — no string-built SQL (codebase already follows this) |
| Rate-limit / budget abuse of sources | DoS | Per-domain token bucket (CMP-02) + per-source caps (`max_items`, requests counter in stats) + 429 → BLOCKED-with-audit |
| Audit-log flooding (per-candidate) | Repudiation (noise) | Run/source-granularity audit events; per-candidate detail in `business_source_records` + stat buckets |
| Secrets in logs (Yelp/Google keys, future OAuth) | Information disclosure | D-18 redaction sink already installed in `main.py`; keys only in `Settings` env fields |

## Sources

### Primary (HIGH confidence)
- **Live robots.txt fetches, 2026-08-05** (`curl`, UA `AIAgencyOS/1.0 (+contact via settings)`): `www.reddit.com` → `User-agent: * / Disallow: /`; `api.reddit.com` → same; `hn.algolia.com` → 404 (no robots.txt); `api.yelp.com` → disallow-all except allowlisted agents (Googlebot etc.); `maps.googleapis.com` → per-UA blocks, no generic allowance
- [hn.algolia.com/api](https://hn.algolia.com/api) — official HN Search API docs: endpoints `/search`, `/search_by_date`, `/items/:id`; tags; **rate limit 10,000 req/hr per IP**
- `.planning/specs/discovery/SPEC-002-lead-discovery-engine.md` — §5.1 sources, §5.2 fields, §5.7 dedup/enrichment (FR-060..064), §7 architecture, §8.2 lead model, §15 security
- `.planning/phases/02-discovery/02-CONTEXT.md` — D-21..D-30 (locked decisions)
- Phase 1 code read: `backend/tools/http_client.py`, `backend/services/compliance/{robots,rate_limit}.py`, `backend/services/audit.py`, `backend/services/scheduler.py`, `backend/database.py`, `backend/config.py`, `backend/api/{approvals,audit}.py`, `backend/main.py`, `tests/conftest.py`, `tests/test_compliance.py`, `pyproject.toml`, `uv.lock`
- `uv.lock` grep: no beautifulsoup4/lxml/rapidfuzz anywhere (zero-dep path confirmed)

### Secondary (MEDIUM confidence — verified with official sources)
- [docs.developer.yelp.com](https://docs.developer.yelp.com/docs/places-faq) — Fusion free tier = 30-day trial (5,000 calls), "STRICTLY FOR EVALUATION AND NOT FOR COMMERCIAL DEPLOYMENT"; daily 5,000-call cap on paid plans
- [terms.yelp.com/developers/api_terms](https://terms.yelp.com/developers/api_terms/20250113_en_us/) — 24h content-caching limit; no generative-AI training on Yelp content (via apio.sh aggregator quotes + Yelp docs)
- [cloud.google.com/maps-platform/terms](https://cloud.google.com/maps-platform/terms) (2020-04-02 snapshot fetched) — "No caching or storage" of Content; listings-service restriction on business-listings Content; 30-day geocode exception only
- [PostgreSQL pg_trgm docs](https://www.postgresql.org/docs/current/pgtrgm.html) — similarity operators, GIN/GiST index support; [Supabase extensions docs](https://supabase.com/docs/guides/database/extensions) — pg_trgm pre-installed
- [Supabase GitHub issue #30503](https://github.com/supabase/supabase/issues/30503) — pg_trgm similarity() not visible despite extension enabled (search_path/schema gotcha)

### Tertiary (LOW confidence — flagged for validation)
- [prowlo.com Reddit Data API 2026](https://prowlo.com/blog/reddit-data-api) (2026-07-22) — unauthenticated .json blocked (403) since late May 2026; official API free tier 100 req/min, commercial use restricted — cross-corroborated by redditapis.com (2026-07-03) and r/redditdev threads (429 reports since 2023)
- [career-ops GitHub issue #1271](https://github.com/santifer/career-ops/issues/1271) — community-verified "Who is hiring" Algolia flow (search_by_date → items/{id} → children) — matches official API docs

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — zero new deps; all elements verified in `pyproject.toml`/`uv.lock`/code
- Architecture: **HIGH** — patterns map 1:1 onto shipped Phase 1 machinery (outbox, audit, compliant client, SSR routers); one required delta (`api_hosts`) flagged as Q1
- Pitfalls: **HIGH for verified facts** (robots.txt live fetches, official API docs), MEDIUM for the 2026 API-terms landscape (third-party reports cross-corroborated but not lawyer-verified)

**Research date:** 2026-08-05
**Valid until:** 2026-09-04 (30 days — source terms/availability shift fast; re-verify HN Algolia + Yelp tiers before Phase 2 execution if longer)
