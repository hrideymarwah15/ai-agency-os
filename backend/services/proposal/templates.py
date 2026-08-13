"""Jinja component rendering for structured proposals."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class ComponentBlock(StrEnum):
    """The ten persisted proposal sections in display order."""

    EXECUTIVE_SUMMARY = "executive_summary"
    AUDIT_REPORT = "audit_report"
    OPPORTUNITY_ANALYSIS = "opportunity_analysis"
    SCOPE = "scope"
    TIMELINE = "timeline"
    PRICING = "pricing"
    FAQS = "faqs"
    TESTIMONIALS = "testimonials"
    TERMS = "terms"
    NEXT_STEPS = "next_steps"


SECTION_ORDER = tuple(ComponentBlock)


class ProposalTemplateEngine:
    """Load safe component templates and assemble the complete proposal HTML."""

    def __init__(self, template_dir: str | Path | None = None) -> None:
        root = Path(template_dir) if template_dir else Path(__file__).resolve().parents[2] / "templates" / "proposals"
        self.environment = Environment(
            loader=FileSystemLoader(root),
            autoescape=select_autoescape(("html", "j2")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @staticmethod
    def _service_key(service_type: str | Any) -> str:
        value = getattr(service_type, "value", service_type)
        return (str(value).lower().replace("ai_chatbot", "chatbot").replace("internal_ai", "custom_ai").replace("automations", "automation"))

    def load_component(self, block: ComponentBlock | str, service_type: str | Any = "website"):
        """Load a service-specific component when present, otherwise its base block."""
        name = ComponentBlock(block).value
        service = self._service_key(service_type)
        candidates = [f"{service}_{name}.j2", f"{name}.j2"]
        for candidate in candidates:
            try:
                return self.environment.get_template(candidate)
            except Exception:
                continue
        raise FileNotFoundError(f"No template for proposal component {name}")

    def render_component(self, block: ComponentBlock | str, context: dict[str, Any]) -> str:
        """Render one proposal component with autoescaped user data."""
        service_type = context.get("service_type", "website")
        return self.load_component(block, service_type).render(**context, section=ComponentBlock(block).value)

    def render_full_proposal(self, context: dict[str, Any]) -> str:
        """Render all ten sections in the canonical order."""
        rendered = {
            block.value: self.render_component(block, context)
            for block in SECTION_ORDER
        }
        return self.environment.get_template("base_proposal.j2").render(
            **context, sections=rendered, section_order=[block.value for block in SECTION_ORDER]
        )
