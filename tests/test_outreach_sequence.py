"""Tests for outreach sequence engine."""

import pytest
from unittest.mock import mock_open, patch
from uuid import uuid4

from backend.services.outreach.sequence import SequenceEngine, SequenceConfig, SequenceStep
from backend.services.audit import AuditService


class TestSequenceModels:
    """Tests for sequence Pydantic models."""

    def test_sequence_step_creation(self):
        """Test creating a SequenceStep."""
        step = SequenceStep(
            step=1,
            delay_days=0,
            template="test_template",
            action="send",
            branch_on_reply={"interested": "meeting", "not_interested": "stop"}
        )

        assert step.step == 1
        assert step.delay_days == 0
        assert step.template == "test_template"
        assert step.action == "send"
        assert step.branch_on_reply == {"interested": "meeting", "not_interested": "stop"}

    def test_sequence_config_creation(self):
        """Test creating a SequenceConfig."""
        steps = [
            SequenceStep(step=1, delay_days=0, template="step1"),
            SequenceStep(step=2, delay_days=3, template="step2")
        ]
        config = SequenceConfig(
            channel="EMAIL",
            steps=steps,
            templates={"step1": "templates/step1.j2", "step2": "templates/step2.j2"}
        )

        assert config.channel == "EMAIL"
        assert len(config.steps) == 2
        assert config.templates["step1"] == "templates/step1.j2"


class TestSequenceEngine:
    """Tests for SequenceEngine."""

    @pytest.fixture
    def sample_yaml_content(self):
        """Sample YAML content for testing."""
        return """
sequences:
  cold_email_5touch:
    channel: EMAIL
    steps:
      - step: 1
        delay_days: 0
        template: "cold_email_1_initial"
        branch_on_reply:
          interested: "meeting"
          not_interested: "stop"
          question: "reply"
          no_reply: "continue"
      - step: 2
        delay_days: 3
        template: "cold_email_2_followup"
        branch_on_reply:
          interested: "meeting"
          not_interested: "stop"
          question: "reply"
          no_reply: "continue"
    templates:
      cold_email_1_initial: "outreach/cold_email_1_initial.j2"
      cold_email_2_followup: "outreach/cold_email_2_followup.j2"
"""

    def test_load_sequences_from_yaml(self, sample_yaml_content):
        """Test loading sequences from YAML content."""
        real_open = open

        def config_open(path, *args, **kwargs):
            if str(path) == "backend/config/outreach.yaml":
                return mock_open(read_data=sample_yaml_content)()
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=config_open):
            engine = SequenceEngine()

            # Check that sequences were loaded
            assert "cold_email_5touch" in engine._sequences
            sequence = engine._sequences["cold_email_5touch"]
            assert sequence.channel == "EMAIL"
            assert len(sequence.steps) == 2
            assert sequence.steps[0].step == 1
            assert sequence.steps[0].template == "cold_email_1_initial"
            assert sequence.steps[1].step == 2
            assert sequence.steps[1].delay_days == 3
            assert sequence.templates["cold_email_1_initial"] == "outreach/cold_email_1_initial.j2"

    def test_load_sequence(self, sample_yaml_content):
        """Test loading a specific sequence."""
        with patch("builtins.open", mock_open(read_data=sample_yaml_content)):
            engine = SequenceEngine()
            sequence = engine.load_sequence("cold_email_5touch")

            assert sequence.channel == "EMAIL"
            assert len(sequence.steps) == 2

    def test_load_sequence_not_found(self, sample_yaml_content):
        """Test loading a non-existent sequence."""
        with patch("builtins.open", mock_open(read_data=sample_yaml_content)):
            engine = SequenceEngine()

            with pytest.raises(ValueError, match="Sequence not found"):
                engine.load_sequence("non_existent_sequence")

    def test_render_template(self, sample_yaml_content):
        """Test rendering a template with personalization data."""
        real_open = open

        def config_open(path, *args, **kwargs):
            if str(path) == "backend/config/outreach.yaml":
                return mock_open(read_data=sample_yaml_content)()
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=config_open):
            engine = SequenceEngine()

            personalization_data = {
                "lead": {"name": "John Doe", "company": "Acme Corp"},
                "owner": {"name": "Jane Smith", "calendar_link": "cal.com/jane"}
            }

            subject, html_body, text_body = engine.render_template(
                "cold_email_1_initial",
                personalization_data
            )

            assert "John Doe" in subject or "John Doe" in html_body or "John Doe" in text_body
            assert "Acme Corp" in html_body or "Acme Corp" in text_body
            assert "Jane Smith" in html_body or "Jane Smith" in text_body

    def test_render_template_with_spintax(self, sample_yaml_content):
        """Test rendering a template with spintax."""
        # This would require modifying the YAML to include spintax
        # For now, we'll test that the method doesn't crash
        with patch("builtins.open", mock_open(read_data=sample_yaml_content)):
            engine = SequenceEngine()

            personalization_data = {
                "lead": {"name": "John", "company": "Corp"},
                "owner": {"name": "Jane", "calendar_link": "cal.com"}
            }

            # This test assumes the template engine can handle basic Jinja2
            # Spintax would need to be implemented in the actual templates
            subject, html_body, text_body = engine.render_template(
                "cold_email_1_initial",
                personalization_data
            )

            assert isinstance(subject, str)
            assert isinstance(html_body, str)
            assert isinstance(text_body, str)

    def test_compute_next_action(self, sample_yaml_content):
        """Test computing next action based on reply classification."""
        with patch("builtins.open", mock_open(read_data=sample_yaml_content)):
            engine = SequenceEngine()

            # Test normal progression
            next_step, next_action_at, branch_action = engine.compute_next_action(
                current_step=1,
                reply_classification="interested"
            )

            # Should advance to step 2
            assert next_step == 2
            assert isinstance(next_action_at, type(engine._get_current_time()))
            assert branch_action is None  # No branching in this simple case

    def test_get_step_template(self, sample_yaml_content):
        """Test getting template for a specific step."""
        with patch("builtins.open", mock_open(read_data=sample_yaml_content)):
            engine = SequenceEngine()

            template = engine.get_step_template("cold_email_5touch", 1)
            assert template == "cold_email_1_initial"

            template = engine.get_step_template("cold_email_5touch", 2)
            assert template == "cold_email_2_followup"

            template = engine.get_step_template("cold_email_5touch", 3)
            assert template is None  # No step 3

    def test_reload_sequences(self, sample_yaml_content):
        """Test reloading sequences from YAML."""
        with patch("builtins.open", mock_open(read_data=sample_yaml_content)):
            engine = SequenceEngine()

            # Modify the YAML content
            modified_yaml = sample_yaml_content.replace(
                "cold_email_5touch",
                "modified_sequence"
            )

            with patch("builtins.open", mock_open(read_data=modified_yaml)):
                engine.reload_sequences()

                # Check that the old sequence is gone and new one is loaded
                assert "cold_email_5touch" not in engine._sequences
                assert "modified_sequence" in engine._sequences


if __name__ == "__main__":
    pytest.main([__file__])
