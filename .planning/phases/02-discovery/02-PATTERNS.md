# Phase 2: Discovery - Pattern Map

**Mapped:** 2026-08-05
**Files analyzed:** 23 grouped rows (9 existing files modified, 14 new file groups)
**Analogs found:** 19 / 23 (codebase now has a full Phase 1 surface — routers, services, templates, tests — so nearly every new file has a concrete shipped analog)

**Codebase reality check:** Phase 1 shipped the full foundation: FastAPI app + lifespan (`backend/main.py`), owner auth (`backend/auth/`), 4 routers (`backend/api/`), 6 services (`backend/services/` incl. `compliance/`), the compliant fetch door (`backend/tools/http_client.py`), 5 templates + `app.css`, Alembic migrations, and 9 test files (86 tests). Phase 2's only genuinely new machinery — the adapter/normalize/dedup/sanitize logic — is pure Python over shipped infrastructure. The `api_hosts` robots exemption (RESEARCH Q1) is the one required Phase 1 delta: `robots.py` + `http_client.py` are self-analogs extended in place, default `∅` keeps all 86 existing tests passing.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/database.py` (mod) | model | CRUD | itself — `AuditLog`/`OutboxEvent`/`ApprovalRequest` + `Business` | exact |
| `backend/config.py` (mod) | config | n/a | itself — `# Compliance`/`mock_mode` sections | exact |
| `backend/tools/http_client.py` (mod) | utility (fetch door) | request-response | itself — `build_compliant_client` | exact |
| `backend/services/compliance/robots.py` (mod) | service | request-response | itself — `RobotsPolicy` | exact |
| `backend/services/scheduler.py` (mod) | service | event-driven | itself — `_heartbeat_job` + `build_scheduler` | exact |
| `backend/main.py` (mod) | controller (app entry) | request-response | itself — lifespan + `include_router` | exact |
| `backend/templates/base.html` (mod) | component | request-response | itself — nav links | exact |
| `backend/static/app.css` (mod) | component (style) | n/a | itself — `:root` tokens + badge classes | exact |
| `backend/alembic/versions/0003_discovery_schema.py` (new) | migration | batch | `0002_audit_append_only_trigger.py` + `e565deca858e_initial_schema.py` | exact |
| `backend/services/discovery/base.py` (new) | service (ABC/interface) | event-driven (stream) | `agents/base.py:71-87` ABC + `compliance/rate_limit.py` class + `database.py:115-120` enum | role-match |
| `backend/services/discovery/registry.py` (new) | service (config dispatch) | n/a | `agents/base.py:118-121` provider dispatch + `config.py` flags | role-match |
| `backend/services/discovery/sources/{hn,reddit,yelp,google_places,mock_directory}.py` (new) | adapter | request-response (fetch→stream) | `compliance/robots.py:55-68` (fetch) + `agents/lead_hunter.py:73-160` (live/mock gate) | role-match |
| `backend/services/discovery/normalize.py` (new) | utility | transform | none — pure fns; RESEARCH Pattern 3 is canonical | none |
| `backend/services/discovery/sanitize.py` (new) | utility | transform | none — pure stdlib; RESEARCH Pattern 4 is canonical | none |
| `backend/services/discovery/dedup.py` (new) | service | CRUD (merge tx) | `services/approvals.py` (service fns + tx + audit) | role-match |
| `backend/services/discovery/enricher.py` (new) | service | request-response | `compliance/robots.py:55-68` fetch + `send_gate.py` decision envelope | role-match |
| `backend/services/discovery/runner.py` (new) | service | batch (orchestration) | `services/approvals.py` (tx shape) + `scheduler.py` session-guard | role-match |
| `backend/services/discovery/worker.py` (new) | service | event-driven (outbox poll) | `main.py:59-80` lifespan + `scheduler.py:64-70` job shape | partial |
| `backend/api/discovery.py` (new) | controller | request-response | `api/approvals.py` + `api/audit.py` | exact |
| `backend/templates/discovery.html` (new) | component | request-response | `audit.html` (table) + `approvals.html` (badges/empty-state) | exact |
| `tests/conftest.py` (mod) | test | n/a | itself — `mock_transport`/`migrated_db`/`test_session` | exact |
| `tests/fixtures/{injections,hn_whoishiring_sample}.json` (new) | fixture | n/a | none — new asset type | none |
| `tests/test_discovery_*.py` (9 new) | test | all | `test_compliance.py` (MockTransport + `_client`) + `test_auth.py` (`_login`) | exact |

## Pattern Assignments

### `backend/database.py` (model, CRUD — MODIFIED)

**Analog:** itself (exact). Extend, don't restructure.

**String enum pattern** (`database.py:115-120`) — new `RunStatus` and `SourceRunStatus` enums copy this shape:
```python
class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"
```
Suggested members per RESEARCH/UI-SPEC: `RunStatus.RUNNING/COMPLETED/PARTIAL/FAILED`; `SourceRunStatus.OK/EMPTY/BLOCKED/ERROR/EXCLUDED/DISABLED` (UI-SPEC §Color badge table).

**Canonical table pattern — the parent-child trio** (`database.py:343-355` AuditLog for the parent; `database.py:442-459` OutboxEvent for the payload+status shape; `database.py:126-159` Business for the master record):
```python
class OutboxEvent(Base):
    """Durable side-effect job queue — ARCHITECTURE.md outbox_events table."""
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING, IN_PROGRESS, DONE, FAILED, DEAD
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    ...
    __table_args__ = (Index("ix_outbox_events_status_next_run_at", "status", "next_run_at"),)
```
New tables go after `OutboxEvent` (line 459), before the `# ==== Database Engine & Session` banner (line 462). Copy shape for: `DiscoveryRun` (id, trigger_source String, status SQLEnum(RunStatus), correlation_id String(64), started_at/finished_at, total_candidates, `Index("ix_discovery_runs_started_at", "started_at")`), `DiscoveryRunSourceStat` (run_id FK→discovery_runs CASCADE, source_id, status SQLEnum(SourceRunStatus), requests_made, found, parsed_ok, rejected, new_count, merged_count, rejection_buckets JSONB — with `UniqueConstraint("run_id", "source_id")` per `LLMSpend:392-396`), `BusinessSourceRecord` (business_id FK→businesses CASCADE, run_id FK, source_id, source_item_id, raw_payload JSONB, sanitized_text Text, status String — per-candidate lineage, D-24).

**Business columns to add** (`database.py:126-159`): `rating` (Numeric(3,1)), `review_count` (Integer), `last_enriched_at` (DateTime tz), `enrichment_version` (Integer default 1), `dedup_key_name/domain/email/phone` (String(255) nullable, + `Index("ix_businesses_dedup_key_domain", "dedup_key_domain")` and same for email/phone — the D-25 exact-match backbone).

**Timestamps:** use the module `utc_now()` helper (`database.py:45-47`) — never `datetime.utcnow` (D-07).

---

### `backend/config.py` (config — MODIFIED)

**Analog:** itself (exact).

**New `# Discovery Sources` section — field pattern** (`config.py:140-149` Compliance + Mock Mode sections):
```python
    # Compliance (CMP-01..04)
    crawler_user_agent: str = Field(
        default="AIAgencyOS/1.0 (+contact via settings)", alias="CRAWLER_USER_AGENT"
    )
    ...
    # Mock Mode (D-20 — dev-only mock agent data, default off)
    mock_mode: bool = Field(default=False, alias="MOCK_MODE")
```
Add (D-21 "unconfigured sources are disabled"): `source_hn_enabled: bool = Field(default=True, alias="SOURCE_HN_ENABLED")`, `source_reddit_enabled` (default False — excluded live), `source_yelp_enabled` / `source_google_places_enabled` (default False — key-gated), `source_mock_directory_enabled` (default False); caps `discovery_max_items_per_source: int = Field(default=50, alias="DISCOVERY_MAX_ITEMS_PER_SOURCE")`; key fields `yelp_api_key` / `google_places_api_key` (default "" — presence gates the key-gated adapters). Section comments group settings (`# Discovery Sources`), same style as lines 84/103/140.

**Config container** (`config.py:331-336` `model_config`) and singleton (`config.py:339-347`) unchanged.

---

### `backend/tools/http_client.py` (utility/fetch door — MODIFIED)

**Analog:** itself (exact). The docstring at lines 1-7 already anticipates this phase.

**`api_hosts` delta — plumb through the factory** (`http_client.py:50-69`):
```python
def build_compliant_client(
    client: httpx.AsyncClient | None = None,
    *,
    session: AsyncSession | None = None,
) -> CompliantHTTPClient:
    """Wire settings into a CompliantHTTPClient sharing one bucket across factories."""
    global _shared_bucket
    inner = client if client is not None else httpx.AsyncClient(timeout=60.0)
    if _shared_bucket is None:
        _shared_bucket = DomainTokenBucket(
            capacity=settings.rate_limit_capacity,
            refill_per_sec=settings.rate_limit_refill_per_sec,
        )
    policy = RobotsPolicy(
        inner,
        user_agent=settings.crawler_user_agent,
        ttl_seconds=settings.robots_cache_ttl_seconds,
        session=session,
    )
    return CompliantHTTPClient(inner, bucket=_shared_bucket, policy=policy)
```
Add `api_hosts: frozenset[str] = frozenset()` keyword param → pass through to `RobotsPolicy(...)`. Default `∅` = Phase 1 behavior (RESEARCH Pattern 5, Q1). The `fetch` pipeline (`http_client.py:37-44`) is untouched: robots → bucket → GET → `raise_for_status()`.

**Error type** (`http_client.py:19-20`) — `RobotsDeniedError(RuntimeError)` is the exclusion signal the runner maps to `RejectReason.BLOCKED`/source status BLOCKED:
```python
class RobotsDeniedError(RuntimeError):
    """Raised when robots.txt denies the fetch — the request is never issued."""
```

---

### `backend/services/compliance/robots.py` (service — MODIFIED)

**Analog:** itself (exact). RESEARCH Pattern 5 delta.

**`api_hosts` exemption + once-per-host audit** (`robots.py:23-53` — extend `__init__` and `can_fetch`):
```python
    async def can_fetch(self, url: str) -> bool:
        """True only when the (cached) robots.txt allows url for our user agent."""
        parsed = urlparse(url)
        host = parsed.hostname or ""
        ...
        parser = await self._load(host, parsed.scheme)
```
Insert before the cache lookup: `if host in self._api_hosts: await self._audit_api_exempt_once(host); return True`. The audit helper copies `_audit_default_deny` (`robots.py:70-82`) — same `AuditService.record(actor="system", ...)` + `await self._session.commit()` shape, new action `api_source_exempt`.

**Fetch + deny-by-default error pattern** (`robots.py:55-68`) — the template for every adapter fetch (see sources below):
```python
    async def _load(self, host: str, scheme: str) -> RobotFileParser | None:
        """Fetch and parse robots.txt for host; None on any failure (deny-by-default)."""
        try:
            response = await self._client.get(f"{scheme}://{host}/robots.txt")
            response.raise_for_status()
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            return parser
        except (httpx.HTTPError, OSError, ValueError):
            logger.warning(
                "robots.txt unavailable for {host} — denying by default", host=host, exc_info=True
            )
            await self._audit_default_deny(host)
            return None
```

---

### `backend/services/scheduler.py` (service, event-driven — MODIFIED)

**Analog:** itself (exact).

**`_discovery_daily_job` — enqueue-only job, exact D-12 shape** (copy `_heartbeat_job`'s session-guard at `scheduler.py:64-70`, then RESEARCH Pattern 2 body):
```python
async def _heartbeat_job() -> None:
    """Upsert the heartbeat row (short, enqueue-only — D-12)."""
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        await write_heartbeat(session, job_name=_HEARTBEAT_JOB_ID)
```
The new job creates `DiscoveryRun(trigger_source="SCHEDULER", status=RunStatus.RUNNING, correlation_id=str(uuid4()))` + `session.add(...)`, `await session.flush()`, `session.add(OutboxEvent(topic="discovery.run", payload={"run_id": str(run.id), "correlation_id": run.correlation_id}))`, `await session.commit()` — never runs the pipeline inline (D-12, Pitfall 8).

**Register in `build_scheduler`** (`scheduler.py:101-129`): new `_DISCOVERY_JOB_ID`, `CronTrigger(hour=...)`, with the same job kwargs `max_instances=1, coalesce=True, misfire_grace_time=60` (lines 108-111 pattern) — the EVENT_JOB_ERROR listener (line 128) already covers it.

---

### `backend/api/discovery.py` (controller, request-response — NEW)

**Analog (exact):** `backend/api/approvals.py` (page + mutating POST + `_check_origin` + flash + 302) and `backend/api/audit.py` (GET page + query params). This is the closest match in the codebase — copy the router skeleton verbatim.

**Router + templates + guards** (`approvals.py:25-27` + `audit.py:16-18`):
```python
router = APIRouter(prefix="/discovery")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
```

**`_check_origin` — copy verbatim** (`approvals.py:51-58`):
```python
def _check_origin(request: Request) -> None:
    """T-03-03: reject cross-origin mutating POSTs with 403 (defense-in-depth)."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    expected = f"{request.url.scheme}://{request.url.netloc}"
    if origin != expected:
        raise HTTPException(status_code=403, detail="Cross-origin request rejected")
```

**GET page pattern** (`audit.py:21-51` — owner-guarded read, flash read/clear, context dict with `active_page`):
```python
@router.get("")
async def audit_page(
    request: Request,
    correlation_id: str | None = None,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    ...
    flash = read_flash(request)
    response = templates.TemplateResponse(
        request,
        "audit.html",
        {
            "entries": entries,
            "flash": flash,
            "agency_name": config.settings.agency_name,
            "owner_email": config.settings.owner_email,
            "active_page": "audit",
            "filter_active": correlation_id is not None,
        },
    )
    clear_flash(response)
    return response
```
The discovery GET passes the UI-SPEC §View Model Contract context instead (`enabled_source_count`, `runs`, `source_columns`, `leads`, `flash`), built by a `_to_view`-style shaper.

**POST trigger pattern** (`approvals.py:118-139` — owner-guarded POST, one transaction, flash + 302; RESEARCH Code Example fills the body):
```python
@router.post("/demo/start")
async def demo_start(
    request: Request,
    _owner: str = Depends(get_current_owner),
) -> Response:
    """Owner-guarded dev trigger: start a gated proposal review (mock_mode only)."""
    _check_origin(request)
    if not config.settings.mock_mode:
        raise HTTPException(status_code=404, detail="Demo trigger requires MOCK_MODE")
    ...
    response = RedirectResponse(url="/approvals", status_code=302)
    set_flash(response, "Demo started — a gated proposal review is waiting for approval.", kind="success")
    return response
```
`POST /discovery/run` body (RESEARCH Code Example + UI-SPEC §Interaction Contract): `_check_origin(request)` → create `DiscoveryRun(trigger_source="MANUAL", status=RunStatus.RUNNING, correlation_id=str(uuid4()))`, `session.add(run); await session.flush()` → `session.add(OutboxEvent(topic="discovery.run", payload={"run_id": str(run.id)}))` → `AuditService.record(session, actor="owner", action="discovery_triggered", entity_type="discovery_run", entity_id=str(run.id), payload={"trigger_source": "MANUAL"}, correlation_id=run.correlation_id)` → `await session.commit()` → 302 `/discovery` + `set_flash(response, "Discovery run queued.", kind="success")`.

**Status-label dicts** — copy `_STATUS_LABELS` shape (`approvals.py:31-37`) for `RunStatus` and `SourceRunStatus` (labels per UI-SPEC §Color: "In progress"/"Complete"/"Partial"/"Failed"; "OK"/"Empty"/"Blocked"/"Error"/"Excluded"/"Disabled"). **Structured-only view model** — copy `_to_view` (`approvals.py:70-88`) and the `_DETAIL_LABELS` whitelist pattern (`approvals.py:39-48`): never pass ORM rows or raw payloads to the template (T-03-01, CMP-06 — `|safe` forbidden on scraped fields).

---

### `backend/services/discovery/base.py` (service/interface, event-driven — NEW)

**Analog (role-match):** `agents/base.py:71-87` (ABC + abstractmethods) + `compliance/rate_limit.py:13-38` (in-process service class) + `database.py:115-120` (enum). **RESEARCH Pattern 1 is the canonical template** — its sketch (`02-RESEARCH.md` §Pattern 1, lines 161-194) is binding; extract from it plus:

**ABC shape** (`agents/base.py:81-87`):
```python
    @abstractmethod
    def get_default_system_prompt(self) -> str:
        """Return the default system prompt for this agent."""

    @abstractmethod
    async def execute(self, task: str, context: AgentContext | None = None) -> dict[str, Any]:
        """Execute a task with the given context."""
```
`SourceAdapter(ABC)` mirrors this: `ClassVar` `source_id`/`display_name`/`api_hosts`/`requires_keys` + `@abstractmethod async def fetch_candidates(self, ctx: RunContext) -> AsyncIterator[SourceCandidate]`. Dataclasses `RunContext`/`SourceCandidate` copy the `@dataclass` shape of `AgentContext` (`agents/base.py:58-68`, `field(default_factory=...)` for mutables). `RejectReason`/`ParseError` copy the `str, enum.Enum` + docstring style; `ParseError(RejectReason)` exception class mirrors `RobotsDeniedError` (`http_client.py:19-20`).

---

### `backend/services/discovery/sources/*.py` (5 adapters — NEW)

**Analog (role-match):** `compliance/robots.py:55-68` (fetch + except + logger.warning) + `agents/lead_hunter.py:73-76,131-160` (MOCK_MODE gate + live fetch + envelope).

**MOCK_MODE gate** (`lead_hunter.py:73-76` — the D-20/D-23 swap is in the registry, not adapter internals):
```python
        if settings.mock_mode:
            return await self._mock_leads(task, count)
        return await self._live_leads(task, count)
```

**Live fetch + error containment** (`lead_hunter.py:150-160` — via the compliant door; note `except Exception` with loguru, never a crash):
```python
        from backend.tools.http_client import build_compliant_client

        try:
            response = await build_compliant_client().fetch(url)
            local_results = response.json().get("local_results", [])
        except Exception as exc:  # noqa: BLE001 — door denial or network failure (CONVENTIONS)
            logger.warning(f"[LeadHunter] live discovery failed: {exc}")
            return {
                "success": True,
                "data": {"leads_discovered": 0, "leads": [], "note": "Live discovery failed"},
            }
```
Adapter deltas: `fetch_candidates` takes `RunContext` (so the client is `ctx.client` — the api_hosts-aware door) and **raises** `ParseError(RejectReason)` per item instead of returning error envelopes (RESEARCH Pattern 1); `RobotsDeniedError`/`httpx.HTTPStatusError` on the source's first request maps to `RejectReason.BLOCKED` and the runner marks the source BLOCKED/EXCLUDED with an audit (LEAD-04 — never retry harder). HN endpoints from RESEARCH §Code Examples (`hn.py`: `SEARCH`/`ITEM` consts at module level, `resp.json()["hits"][0]`, `strip_html_to_text(child.get("text") or "")`, `<4` words → `ParseError(RejectReason.TOO_SHORT)`, `yield SourceCandidate(source_item_id=f"hn:{child['id']}", ...)`).

---

### `backend/services/discovery/registry.py` (service/config dispatch — NEW)

**Analog (role-match):** `agents/base.py:117-121` (config-flag dispatch — the "which provider is live" decision) + `config.py` source flags. Registry maps `source_id` → adapter class + `enabled` flag from `settings` (e.g. `SOURCE_HN_ENABLED`); MOCK_MODE swaps adapter classes (D-23); `source_columns` for the view model comes from registry order (UI-SPEC). No DB table (RESEARCH "env flags, not a DB table"). Registry order = UI-SPEC fixed column order (HN, Reddit, Yelp, G Maps, Mock).

---

### `backend/services/discovery/normalize.py` + `sanitize.py` (utilities, transform — NEW)

**No codebase analog** (no pure-function modules exist yet — `rate_limit.py` is the closest in spirit: small, deterministic, in-process). **RESEARCH Patterns 3 & 4 are canonical and must be copied nearly verbatim** (`02-RESEARCH.md` lines 221-278 — `normalize_domain/phone/email/name`, `_LEGAL_SUFFIXES`, `_TextExtractor(HTMLParser)`, `_CTRL_RE`, `_TOKENS`, `strip_html_to_text`, `strip_control_tokens`). Module conventions to honor: one-line module docstring, `re`/`urllib`/`html.parser` stdlib imports at top, every param/return annotated (mypy `disallow_untyped_defs`), constants as module-level UPPER_SNAKE or `_`-prefixed.

---

### `backend/services/discovery/dedup.py` (service, CRUD/merge — NEW)

**Analog (role-match):** `services/approvals.py` — free async functions over `AsyncSession` with explicit transactions + audits (the codebase's service-function style, NOT classes: `audit.py`/`approvals.py`/`budget.py` are all module-level functions).

**Transaction + audit shape** (`approvals.py:170-179` — audit inside the same transaction as the state change):
```python
    await AuditService.record(
        session,
        actor="owner",
        action="escalated",
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        payload={"reason": row.decision_reason, "request_id": str(row.id)},
        correlation_id=row.context.get("correlation_id"),
    )
    await session.commit()
```

**Query shape** (`approvals.py:90-97` — canonical-key lookup):
```python
    row = (
        await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == request_id))
    ).scalar_one_or_none()
    if row is None:
        raise ValueError(f"Approval request {request_id} not found")
```
Dedup flow (D-25 + RESEARCH Pattern 3): exact lookup on `Business.dedup_key_*` (indexed) → fuzzy secondary pass with `difflib.SequenceMatcher(None, name_a, name_b).ratio() >= 0.85` **AND** a corroborating key (domain or phone) → miss = new `Business` master + `BusinessSourceRecord(status="NEW")`; hit = `merge_into_master` fill-if-missing (RESEARCH Code Example, `_MASTER_FIELDS` tuple) + `BusinessSourceRecord(status="MERGED")`. Same-transaction invariant (Pitfall 5): stats + inserts commit together.

---

### `backend/services/discovery/enricher.py` (service, request-response — NEW)

**Analog (role-match):** `compliance/robots.py:55-68` (fetch pattern) + `send_gate.py`-style decision envelope (`{"allowed": False, "reason": "..."}` — see `test_compliance.py:231-234` assertions) for URL validation.

Homepage scan: validate URL **before** any fetch — scheme ∈ {http, https}, `ipaddress` rejects loopback/private/link-local/ULA, ports 80/443 only, redirect cap ≤ 3 (Pitfall 6) → fetch via `ctx.client` (robots + bucket enforced) → `sanitize.strip_html_to_text` → extract email (`mailto:` + regex), phone, form URL → `merge_into_master`-style fill-if-missing only (FR-062, D-26). Never persist raw HTML (CMP-06).

---

### `backend/services/discovery/runner.py` + `worker.py` (service, batch + event-driven — NEW)

**runner.py analog (role-match):** `services/approvals.py` (function-per-operation over session) + `scheduler.py:66-68` session guard. `execute_run(run_id)` opens the session via `database.async_session_maker` (guard `None` → `RuntimeError("Database not initialized")`), iterates registry sources, per-source: build `RunContext` (run_id, correlation_id, `build_compliant_client(api_hosts=adapter.api_hosts, session=session)`, stat collector), `fetch_candidates` → normalize → sanitize → dedup → enrich, write `DiscoveryRunSourceStat` rows + run totals **in the same transaction** as candidate inserts (Pitfall 5), audit at run/source granularity only (`discovery_run_started` / `source_excluded` / `run_finished` — never per-candidate, RESEARCH Anti-Patterns), final status COMPLETED/PARTIAL/FAILED (Pitfall 4: any source error → PARTIAL).

**worker.py analog (partial):** `main.py:59-80` (lifespan-owned task) + `scheduler.py:64-70` (session-guard job shape). Outbox poll loop: `select(OutboxEvent).where(topic == "discovery.run", status == "PENDING").order_by(created_at)` (AuditService.query shape at `audit.py:47-52`), mark IN_PROGRESS → `await execute_run(run_id)` → DONE (FAILED + `last_error` on exception), `max_instances=1` semantics by serial execution; started in `lifespan`, tracked on `app.state`, cancelled at shutdown (RESEARCH Pattern 2).

---

### `backend/main.py` (controller/app entry — MODIFIED)

**Analog:** itself (exact). Two deltas:

**Include the router** (`main.py:89-93`):
```python
app.include_router(auth_api.router)
app.include_router(approvals_api.router)
app.include_router(audit_api.router)
# Public by design (CMP-04): no Depends(get_current_owner) on the unsubscribe route.
app.include_router(unsubscribe_api.router)
```
→ add `from backend.api import discovery as discovery_api` + `app.include_router(discovery_api.router)`.

**Worker in lifespan** (`main.py:59-80` — start after scheduler, cancel in shutdown):
```python
    scheduler = build_scheduler()
    scheduler.start()
    session_maker = database.async_session_maker
    if session_maker is not None:
        async with session_maker() as session:
            await write_heartbeat(session, job_name="startup")
    yield
    scheduler.shutdown(wait=False)
    await database.close_db()
```
→ `worker_task = asyncio.create_task(discovery_worker())` after heartbeat, `worker_task.cancel()` before `close_db()` (keep the D-18 redaction sink and 401 handler untouched).

---

### `backend/templates/discovery.html` + `base.html` + `app.css` (components — MODIFIED/NEW)

**Analog (exact):** `audit.html` (table + empty-state), `approvals.html` (badges + `<details>/<summary>` + forms), `base.html` nav, `app.css` tokens/badges. UI-SPEC is the binding contract (§Layout, §Component Specs, §Page Anatomy) — every primitive is listed there with its target.

**base.html nav delta** (`base.html:15-20` — add "Discovery" first, `active_page == 'discovery'`):
```html
      <div class="nav__links">
        <a href="/approvals" class="nav-link{% if active_page == 'approvals' %} nav-link--active{% endif %}">
          Approval Queue{% if pending_count and pending_count > 0 %}<span class="nav-badge">{{ pending_count }}</span>{% endif %}
        </a>
        <a href="/audit" class="nav-link{% if active_page == 'audit' %} nav-link--active{% endif %}">Audit Log</a>
      </div>
```

**Table pattern** (`audit.html:23-52` — `scope="col"` headers, `for` loop rows; discovery adds `.table-scroll` wrapper + `.num` cells + `<tfoot>` totals per UI-SPEC §Page Anatomy):
```html
<table class="table">
  <thead>
    <tr>
      <th scope="col">Timestamp</th>
      ...
```
**Badge + empty-state patterns** (`approvals.html:17-18,59-64`): `class="badge badge--{{ status|lower }}"`; `.empty-state` with h2 + p. **Expander** (`approvals.html:23-35` `<details>/<summary>` + `.detail-list`) for per-run source details and lead details. **No `|safe` anywhere on scraped fields** — Jinja2 autoescape is the last line of defense (CMP-06).

**app.css delta** (`app.css:5-20` tokens + `:205-215` badges): add `--blue-text: #1D4ED8; --blue-bg: #DBEAFE;` (the ONLY new `:root` pair, UI-SPEC §Color) + primitives `.table-scroll`, `.num`, `.banner`, `.badge--source`, and semantic aliases `.badge--running/--complete/--partial/--failed/--ok/--empty/--blocked/--error/--excluded/--disabled` mapping onto the existing five pairs (`app.css:211-215`):
```css
  --amber-text: #B45309;  --amber-bg: #FEF3C7;
  --green-text: #15803D;  --green-bg: #DCFCE7;
  --red-text: #B91C1C;    --red-bg: #FEE2E2;
  --violet-text: #7C3AED; --violet-bg: #EDE9FE;
  --slate-text: #475569;  --slate-bg: #F1F5F9;
```

---

### `backend/alembic/versions/0003_discovery_schema.py` (migration — NEW)

**Analog (exact):** `e565deca858e_initial_schema.py` (revision chain + `op.create_table` with `sa.UUID()`, JSONB via `postgresql.JSONB` — see its import of `sqlalchemy.dialects.postgresql`) + `0002_audit_append_only_trigger.py` (down_revision chaining: `revision: str = "0003"`, `down_revision: str | None = "0002"`). Add: `discovery_runs`, `discovery_run_source_stats` (FK + `UniqueConstraint("run_id", "source_id")`), `business_source_records` (FKs, JSONB `raw_payload`), `op.add_column` on `businesses` for the 8 new columns + dedup-key indexes; `op.create_index` for `ix_businesses_dedup_key_*`.

---

### `tests/` (conftest mod + 9 files + 2 fixture JSONs — NEW)

**Analog (exact):** `tests/conftest.py` (fixtures), `tests/test_compliance.py` (MockTransport handlers, `_client`, `compliance_db` cleanup, audit-row assertions), `tests/test_auth.py` (`_login` helper).

**conftest delta:** add a `discovery_db` fixture mirroring `compliance_db` (`test_compliance.py:31-38` — delete the discovery tables before each test):
```python
@pytest.fixture
async def compliance_db(test_session: AsyncSession) -> AsyncSession:
    """Clean the compliance tables the gate/unsubscribe tests write to."""
    await test_session.execute(delete(ConsentRecord))
    await test_session.execute(delete(SuppressionEntry))
    await test_session.execute(delete(OutreachSpend))
    await test_session.commit()
    yield test_session
```
Add fixture JSONs under `tests/fixtures/`: `injections.json` (CMP-06 adversarial payloads incl. `<|endoftext|>` and "ignore previous instructions") and `hn_whoishiring_sample.json` (thread + children, from RESEARCH §Code Examples shape: `{"hits": [{"objectID": ...}], "children": [...]}`).

**Zero-network adapter tests** (`test_compliance.py:41-50` handler factory + `conftest.py:114-122` `mock_transport`):
```python
def _robots_handler(calls: list[str]):
    """MockTransport handler serving a canned robots.txt and counting requests."""
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_ALLOW)
        return httpx.Response(200, text="page-ok")
    return handler
```
HN adapter test pattern from RESEARCH §Code Examples (`test_discovery_sources_hn.py`): handler branches on `/items/` vs search path; `build_compliant_client(mock_transport(handler), api_hosts=frozenset({"hn.algolia.com"}))`.

**API tests** (`test_auth.py:9-22` — login the TestClient, then hit owner-guarded routes):
```python
def _client():
    """TestClient with the app imported AFTER fixtures set the test env."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app, follow_redirects=False)

def _login(client):
    return client.post(
        "/auth/login",
        data={**LOGIN_DATA, "password": conftest.TEST_OWNER_PASSWORD},
    )
```
`test_discovery_api.py` = `_login(client)` → `GET /discovery` (assert 200, run table, badges, empty states) + `POST /discovery/run` (assert 302, flash cookie, `DiscoveryRun` + `OutboxEvent` rows via `test_session`, audit row `discovery_triggered`).

## Shared Patterns

### Owner auth + CSRF on mutating POSTs
**Source:** `backend/auth/owner.py:10-19` (`Depends(get_current_owner)` on every discovery route) + `backend/api/approvals.py:51-58` (`_check_origin` on `POST /discovery/run`). 401 → `/auth/login` handled centrally by `main.py:96-103`.
**Apply to:** `api/discovery.py` both routes; worker runs as `actor="system"` (never the owner dep).

### Flash + redirect round-trip
**Source:** `backend/auth/session.py:33-67` — `set_flash(response, "Discovery run queued.", kind="success")` + 302; page reads `read_flash(request)` and `clear_flash(response)` (`audit.py:37,50`).
**Apply to:** `POST /discovery/run` and the `GET /discovery` page.

### Audit trail with correlation_id
**Source:** `backend/services/audit.py:16-37` — `AuditService.record(session, actor=..., action=..., entity_type=..., entity_id=..., payload=..., correlation_id=...)`; INSERT-only. Run-level events only (`discovery_run_started`, `source_excluded`, `run_finished`, `discovery_triggered`) — never per-candidate (RESEARCH Anti-Patterns).
**Apply to:** trigger endpoint, runner, scheduler job, `api_source_exempt` audit in robots.py.

### Decision envelope for gated/excluded behavior
**Source:** `send_gate.py` / `check_guardrails` — `{"allowed": False, "reason": "consent_required"}` dicts (asserted in `test_compliance.py:231-234`); `RobotsDeniedError` (`http_client.py:19-20`).
**Apply to:** enricher URL validation, source exclusion decisions (BLOCKED/EXCLUDED → audit + stat row, LEAD-04 — never retry harder).

### httpx error handling
**Source:** `http_client.py:37-44` (`raise_for_status()`) + `compliance/robots.py:55-68` (`except (httpx.HTTPError, OSError, ValueError)` → `logger.warning` + audit) + `lead_hunter.py:155-160` (`except Exception` → loguru + non-crash result). Do NOT introduce bare `except:` (CONVENTIONS).
**Apply to:** every adapter, enricher homepage scan, worker (FAILED + `last_error`).

### SQLAlchemy 2.0 async model + session lifecycle
**Source:** `backend/database.py:41-47` (Base + `utc_now`), `:343-459` (AuditLog/ApprovalRequest/OutboxEvent), `:465-508` (globals + `get_db`); `services/approvals.py` (function-per-op + explicit commit + `ValueError` on missing row).
**Apply to:** all 3 new tables, Business column additions, dedup/runner/worker services, migrations env.

### Logging (loguru)
**Source:** `agents/base.py:10` + `scheduler.py:96-98` (`logger.error(f"[scheduler] job failed: ...")`), `robots.py:64-66` (`logger.warning(...)` with kwargs). f-strings with `[{module}]` prefixes; redaction sink already installed in `main.py:41-56` (keys like `yelp_api_key` are auto-scrubbed).
**Apply to:** all new modules; `logger.warning` for source-level failures, `logger.exception` for unexpected.

### Structured-only view model + Jinja2 autoescape
**Source:** `api/approvals.py:39-48,70-88` (`_DETAIL_LABELS` whitelist + `_to_view`) + `audit.html` — templates render only pre-shaped dicts; **never** raw payloads/sanitized text; `|safe` forbidden on scraped fields (T-03-01, CMP-06, UI-SPEC §View Model Contract).
**Apply to:** `api/discovery.py` page route + `discovery.html`.

### Settings singleton + env flags
**Source:** `backend/config.py:331-347` — new `# Discovery Sources` fields with `Field(default=..., alias="SOURCE_*_ENABLED")`; tests monkeypatch via `conftest.py:41-51` (`get_settings.cache_clear()`).
**Apply to:** registry enabled flags, adapter `requires_keys`, caps.

### pytest-asyncio + MockTransport + migrated_db
**Source:** `conftest.py:79-122` (`migrated_db` session fixture, `mock_transport` factory), `test_compliance.py:31-59` (table cleanup + `_client` after env fixtures), `test_auth.py:18-22` (`_login`). Zero network in tests; live HN fetch is a manual/demo path.
**Apply to:** all 9 `test_discovery_*.py` files; `discovery_db` cleanup fixture in conftest.

## No Analog Found

Files with no close codebase match (planner must use RESEARCH.md Patterns 3/4 verbatim — they are the canonical templates):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/services/discovery/normalize.py` | utility | transform | No pure-function module exists in the codebase; RESEARCH Pattern 3 code is the canonical template |
| `backend/services/discovery/sanitize.py` | utility | transform | No stdlib HTMLParser code exists; RESEARCH Pattern 4 code is the canonical template |
| `backend/services/discovery/worker.py` | service | event-driven | Outbox polling is net-new machinery (no poller exists — `OutboxEvent` model is defined but never consumed); shape from `main.py` lifespan + `scheduler.py` job pattern + RESEARCH Pattern 2 |
| `tests/fixtures/injections.json`, `hn_whoishiring_sample.json` | fixture | n/a | No fixture asset files exist yet; content specified in RESEARCH §Code Examples + Validation Architecture |

## Metadata

**Analog search scope:** `backend/` (all 34 py files: tools, services incl. compliance, api, auth, agents, main, database, config), `backend/templates/` (5 templates), `backend/static/app.css`, `backend/alembic/versions/`, `tests/` (9 files), `.planning/phases/01-foundation-orchestration-core/01-PATTERNS.md`, `02-CONTEXT.md`, `02-RESEARCH.md`, `02-UI-SPEC.md`
**Files scanned:** 34 source files, 3 templates, 1 CSS, 2 migrations, 9 test files
**Pattern extraction date:** 2026-08-05
**Key finding:** this is a plumbing-heavy phase over shipped Phase 1 machinery — the only real deltas are (1) the `api_hosts` robots exemption (default-∅, `robots.py` + `http_client.py`), (2) the pure Python adapter/normalize/dedup/sanitize logic (RESEARCH Patterns 1/3/4 verbatim), and (3) the outbox-polling worker (new, but composed from lifespan + job patterns). Every router/page/test has an exact shipped analog (`approvals.py`/`audit.py`, `test_compliance.py`/`test_auth.py`).
