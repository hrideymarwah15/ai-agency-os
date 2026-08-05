"""Lead Hunter Agent - Discovers and enriches business prospects."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from loguru import logger

from backend.agents.base import AgentContext, DiscoveryAgent
from backend.config import settings


class LeadHunterAgent(DiscoveryAgent):
    """Discovers businesses from multiple sources and enriches them."""

    def get_default_system_prompt(self) -> str:
        return f"""You are the Lead Hunter Agent for {settings.agency_name}.
Your mission: Continuously discover high-potential businesses that need our services.

DATA SOURCES TO MONITOR:
1. Google Maps / Places - Local businesses by category
2. Google Search / SerpAPI - Business listings, directories
3. LinkedIn Jobs - Companies hiring for web/dev/automation roles
4. Business Directories - Clutch, GoodFirms, IndiaMART, JustDial
5. Social Platforms - Instagram, Facebook business pages
6. Startup Platforms - Product Hunt, Crunchbase, AngelList
7. Job Boards - Indeed, RemoteOK, Wellfound

TARGET INDUSTRIES & SIGNALS:
- Restaurants: No online ordering, old website, low ratings
- Clinics: No booking system, manual appointments
- Real Estate: No CRM, poor lead capture
- Agencies: Manual client onboarding, no automation
- Schools/Coaching: Manual admissions, no portal
- E-commerce: Poor UX, no automation
- Startups: Need MVP, landing pages, dashboards

ENRICHMENT PRIORITY:
1. Business name, website, contact info
2. Industry, location, employee count
3. Technology stack (CMS, analytics, hosting)
4. Pain points from website audit
5. Growth signals (hiring, funding, expansion)
6. Estimated budget range
7. Decision maker identification

OUTPUT: Structured lead data for scoring and outreach."""

    async def execute(self, task: str, context: AgentContext | None = None) -> dict[str, Any]:
        if context:
            self.set_context(context)

        if "discover" in task.lower():
            return await self._discover_leads(task)
        elif "enrich" in task.lower():
            data = (context.metadata if context else {}).get("business_data", {})
            return {"success": True, "data": await self.enrich_business(data), "raw": None}
        elif "search" in task.lower():
            results = await self.search_businesses(task, "India")
            return {"success": True, "data": {"results": results}}

        messages = self.build_messages(task)
        response = await self.call_llm(messages, temperature=0.5)
        return {"success": True, "data": {"response": response}, "raw": response}

    async def _discover_leads(self, task: str) -> dict[str, Any]:
        """Discover new leads — MOCK_MODE gates the sample data (D-20).

        With mock_mode off the compliant fetch door (robots + rate limit,
        plan 05) handles the request; without a live source configured the
        envelope reports zero leads instead of fabricating them.
        """
        count = settings.daily_lead_discovery_count
        if settings.mock_mode:
            return await self._mock_leads(task, count)
        return await self._live_leads(task, count)

    async def _mock_leads(self, task: str, count: int) -> dict[str, Any]:
        """D-20: structured mock leads behind the mock_mode gate (dev only)."""
        mock_leads = [
            {
                "business_name": "Apex Dental Clinic",
                "industry": "Healthcare",
                "website_url": "https://apex-dental.example.com",
                "email": "contact@apex-dental.example.com",
                "phone": "+91-98765-43210",
                "location": "Mumbai",
                "employee_count": 15,
                "social_links": {"instagram": "@apex.dental", "facebook": "apex.dental.clinic"},
                "tech_stack": ["WordPress", "Google Analytics"],
                "pain_points": [
                    "No online booking",
                    "Manual appointment calls",
                    "No patient portal",
                ],
                "growth_signals": ["Hiring receptionist", "New branch opening"],
                "estimated_budget": 50000,
                "source": "Google Maps",
                "priority_score": 85.0,
            },
            {
                "business_name": "Spice Route Restaurant",
                "industry": "Restaurant",
                "website_url": "https://spiceroute.example.com",
                "email": "info@spiceroute.example.com",
                "phone": "+91-98765-43211",
                "location": "Delhi",
                "employee_count": 25,
                "social_links": {"instagram": "@spiceroute.delhi", "zomato": "spice-route"},
                "tech_stack": ["Wix", "Facebook Pixel"],
                "pain_points": ["No online ordering", "Manual reservations", "No WhatsApp bot"],
                "growth_signals": ["High Zomato rating", "Expanding delivery"],
                "estimated_budget": 40000,
                "source": "Google Maps",
                "priority_score": 92.0,
            },
        ]
        return {
            "success": True,
            "data": {
                "leads_discovered": len(mock_leads),
                "leads": mock_leads[:count],
                "next_actions": [
                    "Run website audits",
                    "Calculate priority scores",
                    "Queue for outreach",
                ],
            },
        }

    async def _live_leads(self, task: str, count: int) -> dict[str, Any]:
        """D-20: real discovery through the compliant fetch door (plan 05)."""
        if not settings.serpapi_key:
            return {
                "success": True,
                "data": {
                    "leads_discovered": 0,
                    "leads": [],
                    "note": "No live lead source configured (SERPAPI_KEY missing); "
                    "enable MOCK_MODE for sample data",
                },
            }
        params = {
            "engine": "google_maps",
            "q": task or "businesses needing websites",
            "location": "Mumbai",
            "api_key": settings.serpapi_key,
        }
        url = "https://serpapi.com/search.json?" + urlencode(params)
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
        leads = [
            {
                "business_name": r.get("title", "Unknown"),
                "industry": r.get("categories", [""])[0] if r.get("categories") else "",
                "website_url": r.get("website") or "",
                "location": r.get("address") or "Mumbai",
                "phone": r.get("phone", ""),
                "source": "SerpAPI",
                "priority_score": 50.0,
            }
            for r in local_results[:count]
        ]
        return {
            "success": True,
            "data": {
                "leads_discovered": len(leads),
                "leads": leads,
                "next_actions": [
                    "Run website audits",
                    "Calculate priority scores",
                    "Queue for outreach",
                ],
            },
        }

    async def search_businesses(self, query: str, location: str, limit: int = 10) -> list[dict]:
        """Search businesses using Google Places or SerpAPI."""
        # Implementation would use actual APIs
        # Placeholder showing expected structure
        return [
            {
                "business_name": f"Sample Business for {query}",
                "industry": query,
                "website_url": "https://example.com",
                "email": "contact@example.com",
                "location": location,
                "employee_count": 20,
                "source": "Google Places",
                "priority_score": 75.0,
            }
        ]

    async def enrich_business(self, business_data: dict) -> dict:
        """Enrich business with additional data points."""
        enriched = business_data.copy()

        # Add missing fields
        enriched.update(
            {
                "tech_stack": business_data.get("tech_stack", []),
                "social_links": business_data.get("social_links", {}),
                "pain_points": business_data.get("pain_points", []),
                "growth_signals": business_data.get("growth_signals", []),
                "estimated_budget": business_data.get("estimated_budget", 0),
                "decision_maker": business_data.get("decision_maker"),
                "enriched_at": datetime.now(UTC).isoformat(),
            }
        )

        return enriched


class MarketScannerAgent(DiscoveryAgent):
    """Scans market for industry trends and competitive intelligence."""

    def get_default_system_prompt(self) -> str:
        return f"""You are the Market Scanner Agent for {settings.agency_name}.
Monitor industry trends, competitor moves, and market opportunities.

SCAN FOR:
1. Industry-specific digital transformation trends
2. Competitor agency pricing and service changes
3. New technology adoption in target industries
4. Regulatory changes affecting digital needs
5. Economic signals in target markets
6. Seasonal demand patterns

OUTPUT: Weekly market intelligence brief with actionable recommendations."""

    async def execute(self, task: str, context: AgentContext | None = None) -> dict[str, Any]:
        messages = self.build_messages(task)
        response = await self.call_llm(messages, temperature=0.4)
        return {"success": True, "data": {"response": response}, "raw": response}
