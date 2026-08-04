"""Core configuration module for AI Agency OS."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Agency Identity
    agency_name: str = Field(default="Nexus AI Agency", alias="AGENCY_NAME")
    agency_owner_email: str = Field(default="owner@example.com", alias="AGENCY_OWNER_EMAIL")
    agency_owner_name: str = Field(default="Agency Owner", alias="AGENCY_OWNER_NAME")
    agency_phone: str = Field(default="+91-9876543210", alias="AGENCY_PHONE")
    agency_address: str = Field(alias="AGENCY_ADDRESS")  # required (CMP-04 physical address)
    default_currency: str = Field(default="INR", alias="DEFAULT_CURRENCY")

    # Database
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_key: str = Field(default="", alias="SUPABASE_KEY")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")
    database_url: str = Field(default="", alias="DATABASE_URL")

    # AI Providers
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    # Model assignments per task
    model_lead_hunter: str = Field(default="openrouter/auto", alias="MODEL_LEAD_HUNTER")
    model_auditor: str = Field(default="groq/llama3-70b-8192", alias="MODEL_AUDITOR")
    model_sales: str = Field(default="openrouter/anthropic/claude-3.5-sonnet", alias="MODEL_SALES")
    model_negotiator: str = Field(
        default="openrouter/anthropic/claude-3.5-sonnet", alias="MODEL_NEGOTIATOR"
    )
    model_developer: str = Field(
        default="openrouter/deepseek/deepseek-coder", alias="MODEL_DEVELOPER"
    )
    model_legal: str = Field(default="openrouter/anthropic/claude-3.5-sonnet", alias="MODEL_LEGAL")

    # Search & Scraping
    google_search_api_key: str = Field(default="", alias="GOOGLE_SEARCH_API_KEY")
    google_cse_id: str = Field(default="", alias="GOOGLE_CSE_ID")
    serpapi_key: str = Field(default="", alias="SERPAPI_KEY")
    playwright_headless: bool = Field(default=True, alias="PLAYWRIGHT_HEADLESS")

    # Email & Communications
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    sendgrid_api_key: str = Field(default="", alias="SENDGRID_API_KEY")
    sendgrid_from_email: str = Field(default="outreach@yourdomain.com", alias="SENDGRID_FROM_EMAIL")

    # WhatsApp
    whatsapp_business_token: str = Field(default="", alias="WHATSAPP_BUSINESS_TOKEN")
    whatsapp_phone_number_id: str = Field(default="", alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_verify_token: str = Field(default="", alias="WHATSAPP_VERIFY_TOKEN")

    # Payments
    razorpay_key_id: str = Field(default="", alias="RAZORPAY_KEY_ID")
    razorpay_key_secret: str = Field(default="", alias="RAZORPAY_KEY_SECRET")
    razorpay_webhook_secret: str = Field(default="", alias="RAZORPAY_WEBHOOK_SECRET")
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: str = Field(default="", alias="STRIPE_PUBLISHABLE_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")

    # Deployment
    vercel_token: str = Field(default="", alias="VERCEL_TOKEN")
    vercel_team_id: str = Field(default="", alias="VERCEL_TEAM_ID")
    cloudflare_api_token: str = Field(default="", alias="CLOUDFLARE_API_TOKEN")
    cloudflare_account_id: str = Field(default="", alias="CLOUDFLARE_ACCOUNT_ID")
    netlify_auth_token: str = Field(default="", alias="NETLIFY_AUTH_TOKEN")

    # Monitoring
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    google_analytics_id: str = Field(default="", alias="GOOGLE_ANALYTICS_ID")

    # Guardrails - Pricing (money as Decimal — D-06)
    min_website_starter: Decimal = Field(default=Decimal("10000.0"), alias="MIN_WEBSITE_STARTER")
    min_website_business: Decimal = Field(default=Decimal("25000.0"), alias="MIN_WEBSITE_BUSINESS")
    min_website_premium: Decimal = Field(default=Decimal("50000.0"), alias="MIN_WEBSITE_PREMIUM")
    min_automation_basic: Decimal = Field(default=Decimal("15000.0"), alias="MIN_AUTOMATION_BASIC")
    min_automation_medium: Decimal = Field(
        default=Decimal("40000.0"), alias="MIN_AUTOMATION_MEDIUM"
    )
    min_automation_advanced: Decimal = Field(
        default=Decimal("80000.0"), alias="MIN_AUTOMATION_ADVANCED"
    )
    min_ai_chatbot_setup: Decimal = Field(default=Decimal("20000.0"), alias="MIN_AI_CHATBOT_SETUP")
    max_discount_percentage: Decimal = Field(
        default=Decimal("15.0"), alias="MAX_DISCOUNT_PERCENTAGE"
    )
    auto_approve_threshold: Decimal = Field(
        default=Decimal("50000.0"), alias="AUTO_APPROVE_THRESHOLD"
    )

    # Budget Caps (FND-06 — per-provider daily LLM spend, hard-blocked in code)
    llm_daily_budget_usd_openrouter: Decimal = Field(
        default=Decimal("5.0"), alias="LLM_DAILY_BUDGET_USD_OPENROUTER"
    )
    llm_daily_budget_usd_groq: Decimal = Field(
        default=Decimal("5.0"), alias="LLM_DAILY_BUDGET_USD_GROQ"
    )
    llm_daily_budget_usd_gemini: Decimal = Field(
        default=Decimal("5.0"), alias="LLM_DAILY_BUDGET_USD_GEMINI"
    )
    llm_cost_usd_per_1k_tokens: dict[str, Decimal] = Field(
        default={
            "openrouter": Decimal("0.50"),
            "groq": Decimal("0.10"),
            "gemini": Decimal("0.25"),
        },
        alias="LLM_COST_USD_PER_1K_TOKENS",
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Scheduler
    daily_lead_discovery_count: int = Field(default=10, alias="DAILY_LEAD_DISCOVERY_COUNT")
    daily_outreach_limit: int = Field(default=25, alias="DAILY_OUTREACH_LIMIT")
    audit_batch_size: int = Field(default=5, alias="AUDIT_BATCH_SIZE")
    maintenance_check_hour: int = Field(default=3, alias="MAINTENANCE_CHECK_HOUR")

    # Owner Auth (D-16 — single owner seeded from env; all required)
    session_secret: str = Field(alias="SESSION_SECRET")
    session_ttl_seconds: int = Field(default=43200, alias="SESSION_TTL_SECONDS")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    owner_email: str = Field(alias="OWNER_EMAIL")
    owner_password_hash: str = Field(alias="OWNER_PASSWORD_HASH")

    # Compliance (CMP-01..04)
    crawler_user_agent: str = Field(
        default="AIAgencyOS/1.0 (+contact via settings)", alias="CRAWLER_USER_AGENT"
    )
    robots_cache_ttl_seconds: int = Field(default=3600, alias="ROBOTS_CACHE_TTL_SECONDS")
    rate_limit_capacity: float = Field(default=1.0, alias="RATE_LIMIT_CAPACITY")
    rate_limit_refill_per_sec: float = Field(default=0.33, alias="RATE_LIMIT_REFILL_PER_SEC")

    # Mock Mode (D-20 — dev-only mock agent data, default off)
    mock_mode: bool = Field(default=False, alias="MOCK_MODE")

    # Service Catalog
    service_catalog: dict = Field(
        default={
            "website": {
                "Starter": {
                    "price": 10000,
                    "monthly": 1500,
                    "features": [
                        "5 Pages",
                        "Responsive",
                        "SEO Basic",
                        "Contact Form",
                        "Analytics Setup",
                    ],
                },
                "Business": {
                    "price": 25000,
                    "monthly": 3000,
                    "features": [
                        "10 Pages",
                        "CMS",
                        "Blog",
                        "SEO Advanced",
                        "Speed Optimization",
                        "Maintenance",
                    ],
                },
                "Premium": {
                    "price": 50000,
                    "monthly": 5000,
                    "features": [
                        "Unlimited Pages",
                        "Custom CMS",
                        "E-commerce Ready",
                        "Full SEO",
                        "Priority Support",
                        "Monthly Updates",
                    ],
                },
                "Enterprise": {
                    "price": 100000,
                    "monthly": 15000,
                    "features": [
                        "Custom Application",
                        "API Integrations",
                        "SSO",
                        "SLA",
                        "Dedicated Support",
                    ],
                },
            },
            "automation": {
                "Basic": {
                    "price": 15000,
                    "monthly": 2500,
                    "features": ["1 Workflow", "n8n Setup", "Basic Integration", "Documentation"],
                },
                "Medium": {
                    "price": 40000,
                    "monthly": 5000,
                    "features": [
                        "3 Workflows",
                        "Custom Nodes",
                        "API Integration",
                        "Monitoring",
                        "Training",
                    ],
                },
                "Advanced": {
                    "price": 80000,
                    "monthly": 10000,
                    "features": [
                        "Unlimited Workflows",
                        "Custom Development",
                        "AI Integration",
                        "24/7 Monitoring",
                        "SLA",
                    ],
                },
            },
            "ai_chatbot": {
                "FAQ Bot": {
                    "setup": 20000,
                    "monthly": 3000,
                    "features": ["Knowledge Base", "FAQ Responses", "Basic Analytics"],
                },
                "Support Bot": {
                    "setup": 35000,
                    "monthly": 8000,
                    "features": [
                        "Ticket Routing",
                        "Escalation",
                        "Multi-language",
                        "CRM Integration",
                    ],
                },
                "Sales Bot": {
                    "setup": 50000,
                    "monthly": 12000,
                    "features": [
                        "Lead Qualification",
                        "Booking",
                        "CRM Sync",
                        "Analytics",
                        "A/B Testing",
                    ],
                },
                "Internal Assistant": {
                    "setup": 60000,
                    "monthly": 15000,
                    "features": ["RAG", "Document Search", "Workflow Automation", "Analytics"],
                },
            },
            "internal_ai": {
                "CRM": {
                    "setup": 50000,
                    "monthly": 10000,
                    "features": ["Lead Management", "Pipeline", "Reports", "Automation"],
                },
                "ERP": {
                    "setup": 100000,
                    "monthly": 25000,
                    "features": ["Inventory", "Finance", "HR", "Analytics", "Custom Modules"],
                },
                "Dashboard": {
                    "setup": 30000,
                    "monthly": 8000,
                    "features": ["Real-time Metrics", "Custom Reports", "Alerts", "Export"],
                },
                "Knowledge Base": {
                    "setup": 25000,
                    "monthly": 5000,
                    "features": ["AI Search", "Version Control", "Access Control", "Analytics"],
                },
            },
        }
    )

    # Industry Multipliers for Dynamic Pricing
    industry_multipliers: dict[str, float] = Field(
        default={
            "Restaurant": 0.9,
            "Healthcare": 1.2,
            "Real Estate": 1.3,
            "Education": 1.0,
            "Legal": 1.4,
            "Technology": 1.3,
            "Finance": 1.5,
            "Retail": 1.0,
            "Hospitality": 1.1,
            "Agency": 1.2,
            "Coaching": 1.1,
            "Startup": 1.2,
            "Ecommerce": 1.2,
            "Manufacturing": 1.1,
            "Non-profit": 0.8,
        }
    )

    # Company Size Multipliers
    size_multipliers: dict[str, float] = Field(
        default={
            "Micro": 0.8,  # 1-10 employees
            "Small": 1.0,  # 11-50 employees
            "Medium": 1.3,  # 51-200 employees
            "Large": 1.7,  # 201-1000 employees
            "Enterprise": 2.0,  # 1000+ employees
        }
    )

    # Urgency Multipliers
    urgency_multipliers: dict[str, float] = Field(
        default={"Normal": 1.0, "Week": 1.15, "3Days": 1.35, "24Hours": 1.6}
    )

    # Website Condition Multipliers
    condition_multipliers: dict[str, float] = Field(
        default={"Excellent": 0.8, "Good": 0.9, "Average": 1.0, "Poor": 1.25, "Critical": 1.5}
    )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    # Required fields load from env/.env at runtime — pydantic-settings default
    return Settings()  # type: ignore[call-arg]


# Export settings instance
settings = get_settings()
