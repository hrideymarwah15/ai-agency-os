# External Integrations

**Analysis Date:** 2026-08-04

## APIs & External Services

**LLM / AI Providers (3 implemented via raw HTTP in `backend/agents/base.py`):**
- **OpenRouter** — primary provider; chat completions at `https://openrouter.ai/api/v1/chat/completions` with `HTTP-Referer` + `X-Title` headers (`backend/agents/base.py:68-87`)
  - SDK/Client: `httpx.AsyncClient` (timeout 60s)
  - Auth: `OPENROUTER_API_KEY`
  - Default model per task: `MODEL_LEAD_HUNTER` (openrouter/auto), `MODEL_SALES`/`MODEL_NEGOTIATOR`/`MODEL_LEGAL` (openrouter/anthropic/claude-3.5-sonnet), `MODEL_DEVELOPER` (openrouter/deepseek/deepseek-coder) — `backend/config.py:32-37`
- **Groq** — fallback provider when OpenRouter key absent; `https://api.groq.com/openai/v1/chat/completions` (`backend/agents/base.py:89-106`)
  - Auth: `GROQ_API_KEY`; default model `MODEL_AUDITOR` (groq/llama3-70b-8192)
- **Gemini (Google AI Studio)** — third fallback; `https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent` with key as query param (`backend/agents/base.py:108-125`)
  - Auth: `GEMINI_API_KEY` (free tier per `.planning/legacy/PROJECT.md`)
  - Provider fallback order: OpenRouter → Groq → Gemini → `"ERROR: No LLM API key configured"` (`backend/agents/base.py:56-63`)
- **Ollama** — local models; only base URL configured (`OLLAMA_BASE_URL`, default `http://localhost:11434`, `backend/config.py:29`) — **no calling code exists**

**Search & Scraping (configured only, no code):**
- Google Search API + Google Custom Search Engine — `GOOGLE_SEARCH_API_KEY`, `GOOGLE_CSE_ID` (`backend/config.py:40-41`); planned for lead discovery per `.planning/specs/discovery/SPEC-002-lead-discovery-engine.md`
- SerpAPI — `SERPAPI_KEY` (`backend/config.py:42`)
- Playwright — browser automation for website audits; `PLAYWRIGHT_HEADLESS` flag (`backend/config.py:43`); `playwright>=1.40.0` declared in `pyproject.toml`; SPEC-002 plans a Playwright crawler pool (Kubernetes 10-50 replicas, Redis + BullMQ queue — planned, not built)

**Email & Communications (configured only, no code):**
- SendGrid — `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` (`backend/config.py:50-51`); `sendgrid>=6.10.0` in `pyproject.toml`
- SMTP (Gmail default) — `SMTP_HOST` (smtp.gmail.com), `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD` (`backend/config.py:46-49`)
- WhatsApp Business (Meta Cloud API) — `WHATSAPP_BUSINESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN` (`backend/config.py:54-56`) — configured, no code

**Payments (configured only, no code):**
- Razorpay — `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` (`backend/config.py:59-61`); `razorpay>=1.4.0` in `pyproject.toml`; default currency INR (`DEFAULT_CURRENCY`)
- Stripe — `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` (`backend/config.py:62-64`); `stripe>=7.0.0` in `pyproject.toml`
- Contract model stores `payment_intent_id` + `payment_schedule` (`backend/database.py:175-180`)

**Deployment Platforms (configured only):**
- Vercel — `VERCEL_TOKEN`, `VERCEL_TEAM_ID` (`backend/config.py:67-68`)
- Cloudflare — `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` (`backend/config.py:69-70`)
- Netlify — `NETLIFY_AUTH_TOKEN` (`backend/config.py:71`)

**Monitoring (configured only):**
- Sentry — `SENTRY_DSN` (`backend/config.py:74`) — no SDK in `pyproject.toml`, no code
- Google Analytics — `GOOGLE_ANALYTICS_ID` (`backend/config.py:75`)

## Data Storage

**Databases:**
- **PostgreSQL (via Supabase)** — primary store; two concurrent access paths in `backend/database.py`:
  1. SQLAlchemy 2.0 async ORM over `DATABASE_URL` (Supabase-hosted Postgres), dialect rewritten to `postgresql+asyncpg://` (`backend/database.py:275-282`); 8 models defined: `Business`, `Audit`, `Proposal`, `Contract`, `Project`, `Task`, `MaintenanceCheck`, `OutreachLog`; tables auto-created via `Base.metadata.create_all` on init (`backend/database.py:284-286`)
  2. Supabase REST client from `SUPABASE_URL` + `SUPABASE_KEY` via `supabase.create_client` (`backend/database.py:288-290`), exposed through `get_supabase()` (`backend/database.py:306`)
- Client: `supabase>=2.3.0` (REST), `asyncpg>=0.29.0` (driver), SQLAlchemy (ORM — undeclared dependency)
- Connection: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY` (service key configured but unused in code)
- pgvector planned for embeddings (`.planning/specs/core/SPEC-001-core-system-architecture.md`, SPEC-002) — not yet used

**File Storage:**
- Local filesystem only; no object storage integration present (object storage for reports/assets is planned per PROJECT.md)

**Caching:**
- Redis declared (`redis>=5.0.0`), `REDIS_URL` default `redis://localhost:6379/0` (`backend/config.py:89`) — **no code uses Redis yet**; specs plan it for queues/message bus (BullMQ mentioned for crawler queue in SPEC-002)

## Authentication & Identity

**Auth Provider:**
- Custom, not yet implemented. `python-jose[cryptography]` (JWT) + `passlib[bcrypt]` (password hashing) declared in `pyproject.toml`; no auth code, no user model exists
- Supabase client could serve as auth backend (`SUPABASE_KEY`) but is only initialized for data access
- Agent approval gate concept (human-owner approvals) exists as config threshold `AUTO_APPROVE_THRESHOLD` (`backend/config.py:86`) and `human_approval_required` flag on Proposal model (`backend/database.py:158`)

## Monitoring & Observability

**Error Tracking:**
- Sentry DSN configured (`backend/config.py:74`) but no `sentry-sdk` dependency and no client code
- LLM failures are caught and logged via `loguru` (`backend/agents/base.py:64-66`)

**Logs:**
- `loguru` (`loguru>=0.7.0`) — structured logging in agents: `logger.info("[{name}] Starting task...")` (`backend/agents/base.py:139`)
- SPEC-001 plans immutable audit log, correlation IDs, PII redaction (planned, not built)

## CI/CD & Deployment

**Hosting:**
- None deployed. No Dockerfile, no docker-compose, no container configs. Planned targets: Vercel/Cloudflare/Netlify (tokens configured), Railway/VPS per PROJECT.md

**CI Pipeline:**
- **None present.** No `.github/`, `.gitlab-ci.yml`, `.circleci/`, Jenkinsfile, or any CI configuration. Git repo has zero commits.

## Environment Configuration

**Required env vars (names only; full documentation in `.env.example`):**
- Identity: `AGENCY_NAME`, `AGENCY_OWNER_EMAIL`, `AGENCY_OWNER_NAME`, `AGENCY_PHONE`, `AGENCY_ADDRESS`, `DEFAULT_CURRENCY`
- Database: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `DATABASE_URL`
- AI: `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OLLAMA_BASE_URL`, `MODEL_LEAD_HUNTER`, `MODEL_AUDITOR`, `MODEL_SALES`, `MODEL_NEGOTIATOR`, `MODEL_DEVELOPER`, `MODEL_LEGAL`
- Search: `GOOGLE_SEARCH_API_KEY`, `GOOGLE_CSE_ID`, `SERPAPI_KEY`, `PLAYWRIGHT_HEADLESS`
- Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`
- WhatsApp: `WHATSAPP_BUSINESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`
- Payments: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- Deployment: `VERCEL_TOKEN`, `VERCEL_TEAM_ID`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `NETLIFY_AUTH_TOKEN`
- Monitoring: `SENTRY_DSN`, `GOOGLE_ANALYTICS_ID`
- Guardrails: `MIN_WEBSITE_STARTER`, `MIN_WEBSITE_BUSINESS`, `MIN_WEBSITE_PREMIUM`, `MIN_AUTOMATION_BASIC`, `MIN_AUTOMATION_MEDIUM`, `MIN_AUTOMATION_ADVANCED`, `MIN_AI_CHATBOT_SETUP`, `MAX_DISCOUNT_PERCENTAGE`, `AUTO_APPROVE_THRESHOLD`
- Infra: `REDIS_URL`, `DAILY_LEAD_DISCOVERY_COUNT`, `DAILY_OUTREACH_LIMIT`, `AUDIT_BATCH_SIZE`, `MAINTENANCE_CHECK_HOUR`

**Secrets location:**
- `.env` file at repo root, loaded by pydantic-settings (`backend/config.py:170`). **`.env` does not exist yet** — only `.env.example` is committed. All secrets reach the app via `backend/config.py` Settings fields.

## Webhooks & Callbacks

**Incoming:**
- **None implemented.** Webhook secrets are configured for Razorpay (`RAZORPAY_WEBHOOK_SECRET`), Stripe (`STRIPE_WEBHOOK_SECRET`), and WhatsApp (`WHATSAPP_VERIFY_TOKEN` — verification handshake) in `backend/config.py`, but no webhook endpoints exist (FastAPI app not yet created).

**Outgoing:**
- **None implemented.** Outreach channel abstraction exists in the `OutreachLog` model (`channel`: EMAIL/WHATSAPP/LINKEDIN, `backend/database.py:252`) and `DiscoveryAgent.search_businesses` / `AuditAgent.audit_website` stubs (`backend/agents/base.py:179-197`), all `NotImplementedError`.

## Integration Status Summary

| Integration | Config | SDK declared | Code implemented |
|---|---|---|---|
| OpenRouter | ✅ | httpx | ✅ `backend/agents/base.py` |
| Groq | ✅ | httpx | ✅ `backend/agents/base.py` |
| Gemini | ✅ | httpx | ✅ `backend/agents/base.py` |
| Ollama | ✅ | — | ❌ |
| Supabase (REST) | ✅ | ✅ | ✅ `backend/database.py` |
| PostgreSQL (asyncpg) | ✅ | ✅ | ✅ `backend/database.py` |
| Redis | ✅ | ✅ | ❌ |
| Playwright | ✅ | ✅ | ❌ |
| SendGrid / SMTP | ✅ | ✅ | ❌ |
| WhatsApp Business | ✅ | — | ❌ |
| Razorpay / Stripe | ✅ | ✅ | ❌ |
| Vercel / Cloudflare / Netlify | ✅ | — | ❌ |
| Sentry / GA | ✅ | ❌ | ❌ |
| SerpAPI / Google Search/CSE | ✅ | — | ❌ |

---

*Integration audit: 2026-08-04*
