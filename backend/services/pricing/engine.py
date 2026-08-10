"""Deterministic pricing engine for AI Agency OS."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from backend.services.pricing.rules import get_pricing_rules
from backend.config import settings


# Pydantic models for pricing engine
class PricingInput(BaseModel):
    """Input parameters for pricing calculation."""
    model_config = ConfigDict(str_strip_whitespace=True)

    hours: float = Field(..., gt=0, description="Estimated hours of work")
    complexity: float = Field(..., ge=1, le=5, description="Complexity level (1-5)")
    market_rate: float = Field(..., gt=0, description="Market rate for similar services")
    competition: float = Field(..., ge=1, le=5, description="Competition level (1-5)")
    industry: str = Field(..., description="Industry sector")
    size: str = Field(..., description="Company size")
    expected_roi: float = Field(..., ge=0, description="Expected ROI percentage")
    historical_close_rate: float = Field(..., ge=0, le=1, description="Historical close rate (0-1)")
    package_name: str = Field(..., description="Service package name")
    service_type: str = Field(..., description="Service type (website, automations, chatbots, custom_ai)")


class NegotiationLimits(BaseModel):
    """Negotiation limits for pricing."""
    can_discount: bool = Field(default=True)
    max_discount_pct: float = Field(..., ge=0, le=100)
    can_bundle: bool = Field(default=True)
    bundle_discount_pct: float = Field(..., ge=0, le=100)
    can_extend_timeline: bool = Field(default=True)
    max_timeline_extension_weeks: int = Field(..., ge=0)
    can_add_maintenance: bool = Field(default=True)
    maintenance_discount_pct: float = Field(..., ge=0, le=100)
    requires_approval_above: float = Field(..., gt=0)


class PricingOutput(BaseModel):
    """Output from pricing calculation."""
    recommended_price: float = Field(..., gt=0, description="Recommended price in INR")
    minimum_price: float = Field(..., gt=0, description="Minimum price in INR")
    target_price: float = Field(..., gt=0, description="Target price in INR")
    max_discount_pct: float = Field(..., ge=0, le=100, description="Maximum discount percentage")
    profit_margin_pct: float = Field(..., description="Profit margin percentage")
    negotiation_limits: NegotiationLimits


class PricingEngine:
    """Deterministic pricing engine that computes prices from weighted factors."""
    
    def __init__(self) -> None:
        self.pricing_rules = get_pricing_rules()
    
    def compute(self, pricing_input: PricingInput) -> PricingOutput:
        """Compute pricing based on input parameters.
        
        Algorithm:
        1. Load package configuration from PricingRules
        2. Base price = sum(scope_matrix line_items.hours * base_rate * complexity_multiplier)
        3. Apply factor weights: each factor contributes (factor_value * weight) to multiplier
        4. Industry multiplier from settings.industry_multipliers, size from settings.size_multipliers
        5. recommended_price = round(base_price * combined_multiplier)
        6. minimum_price = round(recommended_price * (1 - max_discount_pct/100))
        7. target_price = recommended_price (configurable offset)
        8. profit_margin_pct = ((recommended_price - cost_estimate) / recommended_price) * 100
        9. negotiation_limits from package config
        """
        # Load package config
        service_package = self.pricing_rules.get_service_package(
            pricing_input.service_type, 
            pricing_input.package_name
        )
        
        # Get base rate for this service type
        base_rate_per_hour = self.pricing_rules.get_base_rate(pricing_input.service_type)
        
        # Step 2: Calculate base price from scope matrix
        base_price = Decimal('0')
        for line_item in service_package.scope_matrix:
            # Complexity multiplier: basic=1.0, intermediate=1.5, advanced=2.0
            complexity_multiplier = {
                "basic": 1.0,
                "intermediate": 1.5,
                "advanced": 2.0
            }.get(line_item.complexity_tier.lower(), 1.0)
            
            line_item_hours = Decimal(str(line_item.hours))
            line_item_cost = line_item_hours * Decimal(str(base_rate_per_hour)) * Decimal(str(complexity_multiplier))
            base_price += line_item_cost
        
        # Step 3: Apply factor weights
        factor_weights = self.pricing_rules.get_factor_weights()
        combined_factor_multiplier = Decimal('1.0')
        
        # Normalize input values to 0-1 range for factors that need it
        # hours: normalize against a reasonable range (0-200 hours)
        hours_normalized = min(max(pricing_input.hours / 200.0, 0.0), 1.0)
        # complexity: already 1-5, normalize to 0-1
        complexity_normalized = (pricing_input.complexity - 1) / 4.0
        # market_rate: normalize against a reasonable range (0-500000)
        market_rate_normalized = min(max(pricing_input.market_rate / 500000.0, 0.0), 1.0)
        # competition: 1-5, normalize to 0-1 (inverted - less competition is better)
        competition_normalized = (5.0 - pricing_input.competition) / 4.0
        # industry: lookup from settings
        industry_multiplier = Decimal(str(settings.industry_multipliers.get(
            pricing_input.industry.title(), 1.0
        )))
        # size: lookup from settings
        size_multiplier = Decimal(str(settings.size_multipliers.get(
            pricing_input.size.title(), 1.0
        )))
        # expected_roi: normalize against reasonable range (0-1000%)
        expected_roi_normalized = min(max(pricing_input.expected_roi / 1000.0, 0.0), 1.0)
        # historical_close_rate: already 0-1
        historical_close_rate_normalized = pricing_input.historical_close_rate
        
        # Apply weights
        combined_factor_multiplier += (
            Decimal(str(hours_normalized)) * Decimal(str(factor_weights['hours']))
        )
        combined_factor_multiplier += (
            Decimal(str(complexity_normalized)) * Decimal(str(factor_weights['complexity']))
        )
        combined_factor_multiplier += (
            Decimal(str(market_rate_normalized)) * Decimal(str(factor_weights['market_rate']))
        )
        combined_factor_multiplier += (
            Decimal(str(competition_normalized)) * Decimal(str(factor_weights['competition']))
        )
        combined_factor_multiplier *= industry_multiplier  # Industry multiplier multiplies
        combined_factor_multiplier *= size_multiplier      # Size multiplier multiplies
        combined_factor_multiplier += (
            Decimal(str(expected_roi_normalized)) * Decimal(str(factor_weights['expected_roi']))
        )
        combined_factor_multiplier += (
            Decimal(str(historical_close_rate_normalized)) * Decimal(str(factor_weights['historical_close_rate']))
        )
        
        # Step 4: Apply industry and size multipliers (already done above)
        # Step 5: Calculate recommended price
        recommended_price_decimal = base_price * combined_factor_multiplier
        recommended_price = float(round(recommended_price_decimal, 2))
        
        # Step 6: Calculate minimum price
        negotiation_limits = self.pricing_rules.get_negotiation_limits(pricing_input.package_name)
        minimum_price = recommended_price * (1 - negotiation_limits.max_discount_pct / 100)
        minimum_price = round(max(minimum_price, 0.01), 2)  # Ensure minimum is positive
        
        # Step 7: Target price (same as recommended for now, could be configurable)
        target_price = recommended_price
        
        # Step 8: Calculate profit margin
        # Cost estimate: base price (what it costs us to deliver)
        cost_estimate = base_price  # Simplified - in reality would include overhead
        if recommended_price > 0:
            profit_margin_pct = ((recommended_price - float(cost_estimate)) / recommended_price) * 100
        else:
            profit_margin_pct = 0.0
        
        # Step 9: Prepare negotiation limits
        limits_output = NegotiationLimits(
            can_discount=negotiation_limits.can_discount,
            max_discount_pct=negotiation_limits.max_discount_pct,
            can_bundle=negotiation_limits.can_bundle,
            bundle_discount_pct=negotiation_limits.bundle_discount_pct,
            can_extend_timeline=negotiation_limits.can_extend_timeline,
            max_timeline_extension_weeks=negotiation_limits.max_timeline_extension_weeks,
            can_add_maintenance=negotiation_limits.can_add_maintenance,
            maintenance_discount_pct=negotiation_limits.maintenance_discount_pct,
            requires_approval_above=negotiation_limits.requires_approval_above
        )
        
        return PricingOutput(
            recommended_price=recommended_price,
            minimum_price=minimum_price,
            target_price=target_price,
            max_discount_pct=negotiation_limits.max_discount_pct,
            profit_margin_pct=round(profit_margin_pct, 2),
            negotiation_limits=limits_output
        )