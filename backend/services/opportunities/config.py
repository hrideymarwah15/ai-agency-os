"""Configuration loader for opportunities rule engine.

Provides a Pydantic model for the YAML rule config and a helper to load it.
"""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class RuleModel(BaseModel):
    name: str
    category: str  # "automation" | "ai"
    industry: list[str] | None = None
    pattern: str | None = None
    signal: str | None = None
    detection: dict[str, Any] = Field(default_factory=dict)
    recommendation: str
    roi_params: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.8


class RulesConfig(BaseModel):
    automation_rules: list[RuleModel] = []
    ai_rules: list[RuleModel] = []


def load_rules(path: str | Path) -> RulesConfig:
    """Load YAML rule configuration file and validate with Pydantic.

    Args:
        path: Path to the YAML file.
    Returns:
        RulesConfig instance.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return RulesConfig(**data)
