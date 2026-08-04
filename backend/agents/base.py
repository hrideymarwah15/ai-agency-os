"""Base agent class and LLM client for AI Agency OS."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import tenacity
from loguru import logger

from backend import database
from backend.config import settings
from backend.services.budget import BudgetExceededError, reserve_llm

_RETRYABLE_STATUSES = (429, 500, 502, 503, 504)

# Module-level shared client: provider calls use an injected client when given,
# otherwise this lazy singleton (never closed — process-lifetime by design).
_shared_llm_client: httpx.AsyncClient | None = None


def _is_retryable(exc: BaseException) -> bool:
    """True when tenacity should retry the provider request (429/5xx, research A1)."""
    return (
        isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in _RETRYABLE_STATUSES
    )


@tenacity.retry(
    retry=tenacity.retry_if_exception(_is_retryable),
    wait=tenacity.wait_random_exponential(multiplier=0.5, max=8.0),
    stop=tenacity.stop_after_attempt(3),
    reraise=True,
)
async def _post_json(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> httpx.Response:
    """POST JSON to an LLM provider, raising on HTTP errors; retried on 429/5xx."""
    response = await client.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response


def _get_client(client: httpx.AsyncClient | None) -> httpx.AsyncClient:
    """Return the injected client, or the lazy module-level shared client."""
    global _shared_llm_client
    if client is not None:
        return client
    if _shared_llm_client is None:
        _shared_llm_client = httpx.AsyncClient(timeout=60.0)
    return _shared_llm_client


@dataclass
class AgentContext:
    """Shared context passed between agents in a workflow."""

    business_id: str | None = None
    proposal_id: str | None = None
    contract_id: str | None = None
    project_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    conversation_history: list[dict] = field(default_factory=list)


class BaseAgent(ABC):
    """Abstract base class for all agency agents."""

    def __init__(self, name: str, model: str | None = None, system_prompt: str | None = None):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt or self.get_default_system_prompt()
        self.context: AgentContext | None = None
        self.tools: dict[str, Any] = {}

    @abstractmethod
    def get_default_system_prompt(self) -> str:
        """Return the default system prompt for this agent."""

    @abstractmethod
    async def execute(self, task: str, context: AgentContext | None = None) -> dict[str, Any]:
        """Execute a task with the given context."""

    def set_context(self, context: AgentContext) -> None:
        self.context = context

    def register_tool(self, name: str, func: Callable[..., Any]) -> None:
        self.tools[name] = func

    async def _reserve_budget(self, provider: str, max_tokens: int) -> None:
        """Reserve estimated spend against the provider's daily cap (D-11, hard block)."""
        cost_usd_per_1k = settings.llm_cost_usd_per_1k_tokens.get(provider)
        if cost_usd_per_1k is None:
            return
        cost_cents = max(1, int(cost_usd_per_1k * max_tokens / 1000 * 100))
        session_maker = database.async_session_maker
        if session_maker is None:
            raise RuntimeError("Database not initialized")
        async with session_maker() as session:
            await reserve_llm(
                session, provider=provider, model=self.model or "default", cost_cents=cost_cents
            )

    async def call_llm(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        client: httpx.AsyncClient | None = None,
    ) -> str:
        """Call LLM via OpenRouter, Groq, or Gemini — budget-gated before any provider contact."""
        try:
            if settings.openrouter_api_key:
                provider = "openrouter"
            elif settings.groq_api_key:
                provider = "groq"
            elif settings.gemini_api_key:
                provider = "gemini"
            else:
                return "ERROR: No LLM API key configured"

            try:
                await self._reserve_budget(provider, max_tokens)
            except BudgetExceededError as e:
                logger.error(f"[{self.name}] Budget exceeded: {e}")
                return "ERROR: budget exceeded"

            if provider == "openrouter":
                return await self._call_openrouter(messages, temperature, max_tokens, client)
            if provider == "groq":
                return await self._call_groq(messages, temperature, max_tokens, client)
            return await self._call_gemini(messages, temperature, max_tokens, client)
        except Exception as e:  # noqa: BLE001 — CONVENTIONS §Error Handling mandates
            # a broad catch that turns every provider/DB failure into an ERROR string.
            logger.error(f"LLM call failed for {self.name}: {e}")
            return f"ERROR: {e!s}"

    async def _call_openrouter(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        client: httpx.AsyncClient | None = None,
    ) -> str:
        response = await _post_json(
            _get_client(client),
            "https://openrouter.ai/api/v1/chat/completions",
            {
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ai-agency-os.local",
                "X-Title": "AI Agency OS",
            },
            {
                "model": self.model or "openrouter/auto",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        content: Any = response.json()["choices"][0]["message"]["content"]
        return str(content)

    async def _call_groq(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        client: httpx.AsyncClient | None = None,
    ) -> str:
        response = await _post_json(
            _get_client(client),
            "https://api.groq.com/openai/v1/chat/completions",
            {
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.model or "llama3-70b-8192",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        content: Any = response.json()["choices"][0]["message"]["content"]
        return str(content)

    async def _call_gemini(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        client: httpx.AsyncClient | None = None,
    ) -> str:
        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        # D-18: key goes in the X-Goog-Api-Key header — never in the URL query.
        response = await _post_json(
            _get_client(client),
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model or 'gemini-pro'}:generateContent",
            {
                "X-Goog-Api-Key": settings.gemini_api_key,
                "Content-Type": "application/json",
            },
            {
                "contents": contents,
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            },
        )
        content: Any = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return str(content)

    def build_messages(self, user_prompt: str) -> list[dict]:
        """Build message list with system prompt and history."""
        messages = [{"role": "system", "content": self.system_prompt}]

        if self.context and self.context.conversation_history:
            messages.extend(self.context.conversation_history[-10:])  # Last 10 exchanges

        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def run(self, task: str) -> dict[str, Any]:
        """Main entry point for agent execution."""
        logger.info(f"[{self.name}] Starting task: {task[:100]}...")
        result = await self.execute(task, self.context)
        logger.info(f"[{self.name}] Completed task")
        return result


class LLMAgent(BaseAgent):
    """LLM-powered agent with structured output parsing."""

    def __init__(
        self,
        name: str,
        model: str | None = None,
        system_prompt: str | None = None,
        output_schema: dict | None = None,
    ):
        super().__init__(name, model, system_prompt)
        self.output_schema = output_schema

    async def execute(self, task: str, context: AgentContext | None = None) -> dict[str, Any]:
        if context:
            self.set_context(context)

        messages = self.build_messages(task)
        response = await self.call_llm(messages)

        if self.output_schema:
            # Try to parse structured output
            try:
                import json

                # Extract JSON from response
                start = response.find("{")
                end = response.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(response[start:end])
                    return {"success": True, "data": parsed, "raw": response}
            except (ValueError, TypeError):
                pass

        return {"success": True, "data": {"response": response}, "raw": response}


# Specialized Agent Base Classes
class DiscoveryAgent(BaseAgent):
    """Agents that discover and enrich leads."""

    async def search_businesses(self, query: str, location: str, limit: int = 10) -> list[dict]:
        """Search for businesses using available APIs."""
        raise NotImplementedError

    async def enrich_business(self, business_data: dict) -> dict:
        """Enrich business with additional data."""
        raise NotImplementedError


class AuditAgent(BaseAgent):
    """Agents that audit websites and digital presence."""

    async def audit_website(self, url: str) -> dict:
        """Perform comprehensive website audit."""
        raise NotImplementedError

    async def analyze_technologies(self, url: str) -> dict:
        """Detect CMS, frameworks, analytics, etc."""
        raise NotImplementedError


class SalesAgent(BaseAgent):
    """Agents that handle outreach and sales."""

    async def generate_outreach(self, business_data: dict, audit_data: dict) -> dict:
        """Generate personalized outreach message."""
        raise NotImplementedError

    async def handle_objection(self, objection: str, context: dict) -> dict:
        """Handle sales objection."""
        raise NotImplementedError


class NegotiationAgent(BaseAgent):
    """Agents that negotiate within guardrails."""

    async def negotiate(self, client_offer: float, proposal_data: dict) -> dict:
        """Negotiate price within guardrails."""
        raise NotImplementedError

    def check_guardrails(self, offered_price: float, min_price: float) -> dict:
        """Check if offer respects guardrails."""
        if offered_price < min_price:
            return {"allowed": False, "min_price": min_price, "reason": "Below minimum price"}
        return {"allowed": True}


class DeliveryAgent(BaseAgent):
    """Agents that build and deploy projects."""

    async def create_project_plan(self, contract_data: dict) -> dict:
        """Create detailed project plan with tasks."""
        raise NotImplementedError

    async def build_deliverable(self, task: dict) -> dict:
        """Build a specific deliverable."""
        raise NotImplementedError

    async def deploy(self, project_data: dict) -> dict:
        """Deploy completed project."""
        raise NotImplementedError


class OpsAgent(BaseAgent):
    """Agents that handle operations, maintenance, and support."""

    async def run_maintenance_check(self, project_id: str) -> dict:
        """Run scheduled maintenance check."""
        raise NotImplementedError

    async def generate_report(self, project_id: str, check_data: dict) -> dict:
        """Generate client-facing maintenance report."""
        raise NotImplementedError
