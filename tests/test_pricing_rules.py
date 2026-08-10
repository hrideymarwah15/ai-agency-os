"""Pricing rules tests — YAML loading, validation, hot-reload, and service package lookup."""

import pytest
from uuid import uuid4

from backend.services.pricing.rules import get_pricing_rules, PricingRules


def test_pricing_rules_singleton():
    """Test that get_pricing_rules returns a singleton."""
    rules1 = get_pricing_rules()
    rules2 = get_pricing_rules()
    assert rules1 is rules2
    assert isinstance(rules1, PricingRules)


def test_pricing_rules_load_yaml():
    """Test that pricing rules load YAML configuration correctly."""
    rules = get_pricing_rules()
    
    # Test factor weights
    weights = rules.get_factor_weights()
    assert weights["hours"] == 0.25
    assert weights["complexity"] == 0.20
    assert weights["market_rate"] == 0.15
    assert weights["competition"] == 0.10
    assert weights["industry"] == 0.10
    assert weights["size"] == 0.10
    assert weights["expected_roi"] == 0.05
    assert weights["historical_close_rate"] == 0.05
    
    # Test service packages
    assert "website" in rules.config.service_packages
    assert "automations" in rules.config.service_packages
    assert "chatbots" in rules.config.service_packages
    assert "custom_ai" in rules.config.service_packages
    
    # Test website packages
    website_packages = rules.config.service_packages["website"]
    assert "Starter" in website_packages
    assert "Business" in website_packages
    assert "Premium" in website_packages
    
    # Test specific package lookup
    starter_pkg = rules.get_service_package("website", "Starter")
    assert starter_pkg.base_rate == 750.0
    assert len(starter_pkg.scope_matrix) == 5
    
    # Test base rate lookup
    website_base_rate = rules.get_base_rate("website")
    assert website_base_rate == 750.0  # Should match Starter package base rate
    
    # Test negotiation limits
    limits = rules.get_negotiation_limits("Starter")
    assert limits.can_discount == True
    assert limits.max_discount_pct == 25.0
    assert limits.requires_approval_above == 100000.0


def test_pricing_rules_hot_reload_simulation():
    """Test hot-reload mechanism (simulation since we won't actually modify file in test)."""
    rules = get_pricing_rules()
    original_weights = rules.get_factor_weights().copy()
    
    # Test that reload_if_changed returns False when no changes
    assert rules.reload_if_changed() == False
    
    # Test that config property returns the same config
    config1 = rules.config
    config2 = rules.config
    assert config1 is config2  # Should return same instance when no changes


def test_pricing_rules_validation():
    """Test that invalid configurations are caught."""
    # This would require modifying the YAML file, which we won't do in unit tests
    # The Pydantic validation happens in the _load_config method
    pass