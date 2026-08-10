"""Pricing API tests — route registration and basic functionality."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.pricing.rules import get_pricing_rules


def test_pricing_routes_exist():
    """Test that pricing routes are registered in the app."""
    client = TestClient(app)
    
    # Test that we can access the API docs (implies routes are registered)
    response = client.get("/docs")
    assert response.status_code == 200
    
    # Test OpenAPI schema includes pricing routes
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    
    # Check that pricing paths exist in the schema
    paths = schema.get("paths", {})
    assert "/pricing/calculate" in paths
    assert "/pricing/rules" in paths
    assert "/pricing/runs" in paths
    # Note: PUT /pricing/rules/{rule_id} is harder to test without knowing the exact path format


def test_pricing_rules_endpoint():
    """Test the GET /pricing/rules endpoint."""
    client = TestClient(app)
    
    # This would require authentication in a real test
    # For now, we'll just verify the route exists by checking that it doesn't return 404
    response = client.get("/pricing/rules")
    # Expecting either 200 (if auth bypassed in test) or 401/403 (if auth required)
    # Either way, it shouldn't be 404 (not found)
    assert response.status_code != 404


def test_pricing_calculate_endpoint_exists():
    """Test that the POST /pricing/calculate endpoint exists."""
    client = TestClient(app)
    
    # Test with empty body to see if we get a validation error (means route exists)
    response = client.post("/pricing/calculate", json={})
    # Should get 422 (validation error) not 404 (not found)
    assert response.status_code != 404


def test_pricing_get_pricing_rules_function():
    """Test that the pricing rules function works correctly."""
    # This tests the backend function that the API uses
    get_pricing_rules()  # Initialize
    rules = get_pricing_rules()
    
    # Test that we can get the configuration
    config = rules.config
    assert config is not None
    assert hasattr(config, 'factor_weights')
    assert hasattr(config, 'service_packages')
    
    # Test factor weights
    weights = rules.get_factor_weights()
    assert isinstance(weights, dict)
    assert "hours" in weights
    assert "complexity" in weights
    
    # Test service packages
    assert "website" in config.service_packages
    assert isinstance(config.service_packages["website"], dict)


def test_pricing_engine_integration():
    """Test that pricing engine works with the rules system."""
    get_pricing_rules()
    from backend.services.pricing.engine import PricingEngine, PricingInput
    
    engine = PricingEngine()
    
    # Test computation
    input_data = PricingInput(
        package_name="Starter",
        service_type="website",
        hours=10.0,
        complexity=2.0,
        market_rate=20000.0,
        competition=2.0,
        industry="technology",
        size="small",
        expected_roi=50.0,
        historical_close_rate=0.1
    )
    
    output = engine.compute(input_data)
    assert output.recommended_price > 0
    assert output.minimum_price > 0
    assert isinstance(output.profit_margin_pct, float)