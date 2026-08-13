"""Outreach sequence engine: template rendering, personalization, branching logic."""

from datetime import datetime, timedelta, timezone
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

class SequenceStep(BaseModel):
    """Single step in an outreach sequence."""
    step: int = Field(..., ge=1, description="Step number (1-indexed)")
    delay_days: int = Field(..., ge=0, description="Days to wait after previous step")
    template: str = Field(..., description="Jinja2 template name")
    action: str = Field(default="send", description="Action type: send, connection_request, message")
    branch_on_reply: Optional[Dict[str, str]] = Field(
        default=None,
        description="Mapping of reply classification to next step/action: e.g. {'interested': 'meeting', 'not_interested': 'stop'}"
    )
    condition: Optional[str] = Field(
        default=None,
        description="Condition that must be true to execute this step (e.g. 'connection_accepted')"
    )
    # New fields for 03-03
    follow_up_trigger: Optional[str] = Field(
        default=None,
        description="Trigger for automatic follow-up (e.g. '3_days_no_reply', 'email_opened')"
    )
    is_breakup_step: bool = Field(
        default=False,
        description="Whether this step is part of a breakup sequence"
    )
    is_re_engagement_step: bool = Field(
        default=False,
        description="Whether this step is part of a re-engagement campaign"
    )


class SequenceConfig(BaseModel):
    """Complete outreach sequence configuration."""
    channel: str = Field(..., description="Channel: EMAIL, LINKEDIN, etc.")
    steps: List[SequenceStep] = Field(..., min_items=1, description="Sequence steps in order")
    templates: Optional[Dict[str, str]] = Field(
        default=None,
        description="Mapping of template names to Jinja2 template paths"
    )
    # New fields for 03-03 - loaded from global settings in outreach.yaml
    objection_responses: Optional[Dict[str, str]] = Field(
        default=None,
        description="Predefined responses for common objections"
    )
    follow_up_triggers: Optional[Dict[str, List[Dict[str, Any]]]] = Field(
        default=None,
        description="Time-based and trigger-based follow-up automation rules"
    )
    breakup_sequence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Breakup sequence configuration for non-responders"
    )
    re_engagement_campaign: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Re-engagement campaign configuration for old leads"
    )
    meeting_link_template: Optional[str] = Field(
        default=None,
        description="Template for generating personalized meeting links"
    )


class SequenceEngine:
    """Engine for loading sequences, rendering templates, and computing next actions."""

    def __init__(self):
        self._sequences: Dict[str, SequenceConfig] = {}
        self._template_env: Optional[Environment] = None
        self._load_sequences()

    def _load_sequences(self) -> None:
        """Load sequences from outreach.yaml file."""
        try:
            with open("backend/config/outreach.yaml", "r") as f:
                config = yaml.safe_load(f)

            # Load sequences
            sequences_data = config.get("sequences", {})
            global_templates = config.get("templates", {})
            for seq_id, seq_data in sequences_data.items():
                # Convert steps to SequenceStep objects
                steps = []
                for step_data in seq_data.get("steps", []):
                    steps.append(SequenceStep(**step_data))

                # Create SequenceConfig with global settings
                sequences_data[seq_id] = SequenceConfig(
                    channel=seq_data["channel"],
                    steps=steps,
                    templates={**global_templates, **seq_data.get("templates", {})},
                    # Load global settings for this sequence
                    objection_responses=config.get("objection_responses"),
                    follow_up_triggers=config.get("follow_up_triggers"),
                    breakup_sequence=config.get("breakup_sequence"),
                    re_engagement_campaign=config.get("re_engagement_campaign"),
                    meeting_link_template=config.get("meeting_link_template")
                )

            self._sequences = sequences_data

            # Setup Jinja2 template environment
            template_dirs = ["backend/templates"]
            self._template_env = Environment(
                loader=FileSystemLoader(template_dirs),
                autoescape=select_autoescape(['html', 'xml']),
                enable_async=True
            )

        except FileNotFoundError:
            # Fallback to empty sequences if config missing
            self._sequences = {}
            self._template_env = Environment(
                loader=FileSystemLoader(["backend/templates"]),
                autoescape=select_autoescape(['html', 'xml'])
            )

    def load_sequence(self, sequence_id: str) -> SequenceConfig:
        """Load a sequence by ID."""
        if sequence_id not in self._sequences:
            raise ValueError(f"Sequence not found: {sequence_id}")
        return self._sequences[sequence_id]

    def render_template(self, template_name: str, personalization_data: Dict[str, Any]) -> Tuple[str, str, str]:
        """
        Render a Jinja2 template with personalization data.

        Returns:
            Tuple of (subject, html_body, text_body)
        """
        if not self._template_env:
            raise RuntimeError("Template environment not initialized")

        # Determine template path from outreach.yaml or use default mapping
        template_path = self._get_template_path(template_name)

        try:
            template = self._template_env.get_template(template_path)
            rendered = self.render_spintax(template.render(**personalization_data))

            # Simple parsing: assume first line is subject, rest is body
            lines = rendered.strip().split('\n', 1)
            if len(lines) == 2:
                subject, body = lines
            else:
                subject = f"Message regarding {personalization_data.get('lead', {}).get('company', 'your business')}"
                body = rendered

            # For simplicity, use same body for HTML and text (could be enhanced)
            return subject.strip(), body, body

        except Exception:
            # Fallback to basic template on error
            subject = f"Hello {personalization_data.get('lead', {}).get('name', 'there')}"
            body = f"Hi {personalization_data.get('lead', {}).get('name', 'there')},\n\nWe help businesses like {personalization_data.get('lead', {}).get('company', 'theirs')} grow.\n\nBest regards,\n{personalization_data.get('owner', {}).get('name', 'The Team')}"
            return subject, body, body

    def _get_template_path(self, template_name: str) -> str:
        """Get the actual template path for a template name."""
        # Check if we have explicit template mapping in sequences
        for seq_config in self._sequences.values():
            if seq_config.templates and template_name in seq_config.templates:
                return seq_config.templates[template_name]

        # Default mapping: assume templates/outreach/{template_name}.j2
        # But first check if it's already a path
        if template_name.endswith('.j2'):
            return template_name
        return f"outreach/{template_name}.j2"

    def compute_next_action(
        self,
        current_step: int,
        reply_classification: Optional[str] = None,
        condition_results: Optional[Dict[str, bool]] = None
    ) -> Tuple[Optional[int], Optional[datetime], Optional[str]]:
        """
        Compute the next step based on current step and reply classification.

        Returns:
            Tuple of (next_step_number, next_action_at, branch_action)
            Returns (None, None, None) if sequence is complete
        """
        if not self._sequences:
            return None, None, None

        # We need to know which sequence we're in - this should be passed in
        # For now, we'll assume the caller manages sequence context
        # This is a simplified version - in practice, sequence_id would be stored with the campaign

        # Placeholder implementation - this would be enhanced with sequence context
        # For the MVP, we'll return a basic next step calculation
        next_step = current_step + 1
        next_action_at = self._get_current_time() + timedelta(days=3)  # Default 3 day delay

        # Check if we've exceeded max steps (would need sequence config)
        # For now, assume max 5 steps
        if next_step > 5:
            return None, None, None

        return next_step, next_action_at, None

    def _get_current_time(self) -> datetime:
        """Return an aware UTC timestamp for deterministic test patching."""
        return datetime.now(timezone.utc)

    def render_spintax(self, text: str) -> str:
        """Resolve simple ``{option one|option two}`` spintax expressions."""
        pattern = re.compile(r"\{([^{}|]+(?:\|[^{}|]+)+)\}")
        while match := pattern.search(text):
            text = text[: match.start()] + random.choice(match.group(1).split("|")) + text[match.end() :]
        return text

    def get_step_template(self, sequence_id: str, step_number: int) -> Optional[str]:
        """Get the template name for a specific step in a sequence."""
        if sequence_id not in self._sequences:
            return None

        config = self._sequences[sequence_id]
        for step in config.steps:
            if step.step == step_number:
                return step.template
        return None

    def reload_sequences(self) -> None:
        """Reload sequences from YAML file (for hot-reload)."""
        self._load_sequences()

    def get_objection_response(self, objection_type: str) -> Optional[str]:
        """Get a predefined response for a specific objection type."""
        # Return the first sequence's objection response (they're all the same)
        for sequence_config in self._sequences.values():
            if sequence_config.objection_responses:
                return sequence_config.objection_responses.get(objection_type)
        return None

    def get_follow_up_triggers(
        self, sequence_id: Optional[str] = None
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """Get follow-up trigger configuration."""
        if sequence_id is not None:
            return self.load_sequence(sequence_id).follow_up_triggers
        for sequence_config in self._sequences.values():
            if sequence_config.follow_up_triggers:
                return sequence_config.follow_up_triggers
        return None

    def get_breakup_sequence(self) -> Optional[Dict[str, Any]]:
        """Get breakup sequence configuration."""
        # Return the first sequence's breakup sequence (they're all the same)
        for sequence_config in self._sequences.values():
            if sequence_config.breakup_sequence:
                return sequence_config.breakup_sequence
        return None

    def get_re_engagement_campaign(self) -> Optional[Dict[str, Any]]:
        """Get re-engagement campaign configuration."""
        # Return the first sequence's re-engagement campaign (they're all the same)
        for sequence_config in self._sequences.values():
            if sequence_config.re_engagement_campaign:
                return sequence_config.re_engagement_campaign
        return None

    def get_meeting_link_template(self) -> Optional[str]:
        """Get meeting link template."""
        # Return the first sequence's meeting link template (they're all the same)
        for sequence_config in self._sequences.values():
            if sequence_config.meeting_link_template:
                return sequence_config.meeting_link_template
        return None

    def is_follow_up_step(self, step: SequenceStep) -> bool:
        """Check if a step is a follow-up trigger step."""
        return step.follow_up_trigger is not None

    def is_breakup_step(self, step: SequenceStep) -> bool:
        """Check if a step is part of a breakup sequence."""
        return step.is_breakup_step

    def is_re_engagement_step(self, step: SequenceStep) -> bool:
        """Check if a step is part of a re-engagement campaign."""
        return step.is_re_engagement_step
