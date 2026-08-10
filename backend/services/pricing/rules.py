"""Pricing rules engine with hot-reload capability."""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, ValidationError

from backend.config import settings


# Pydantic models for pricing configuration
class FactorWeights(BaseModel):
    hours: float = Field(..., ge=0, le=1)
    complexity: float = Field(..., ge=0, le=1)
    market_rate: float = Field(..., ge=0, le=1)
    competition: float = Field(..., ge=0, le=1)
    industry: float = Field(..., ge=0, le=1)
    size: float = Field(..., ge=0, le=1)
    expected_roi: float = Field(..., ge=0, le=1)
    historical_close_rate: float = Field(..., ge=0, le=1)


class ScopeMatrixItem(BaseModel):
    item: str
    hours: float = Field(..., gt=0)
    complexity_tier: str  # basic, intermediate, advanced


class ServicePackage(BaseModel):
    scope_matrix: list[ScopeMatrixItem]
    base_rate: float = Field(..., gt=0)  # INR per hour


class DynamicAdjustments(BaseModel):
    volume_bundles: dict[str, Any] = Field(default_factory=dict)
    long_term_contracts: dict[str, Any] = Field(default_factory=dict)
    referral_partner_discounts: dict[str, Any] = Field(default_factory=dict)
    seasonal_promos: dict[str, Any] = Field(default_factory=dict)


class NegotiationLimits(BaseModel):
    can_discount: bool = True
    max_discount_pct: float = Field(..., ge=0, le=100)
    can_bundle: bool = True
    bundle_discount_pct: float = Field(..., ge=0, le=100)
    can_extend_timeline: bool = True
    max_timeline_extension_weeks: int = Field(..., ge=0)
    can_add_maintenance: bool = True
    maintenance_discount_pct: float = Field(..., ge=0, le=100)
    requires_approval_above: float = Field(..., gt=0)  # INR


class PricingConfig(BaseModel):
    factor_weights: FactorWeights
    service_packages: dict[str, dict[str, ServicePackage]]
    dynamic_adjustments: DynamicAdjustments
    negotiation_limits: NegotiationLimits
    base_rates: dict[str, float] = Field(default_factory=dict)


class PricingRules:
    """Singleton pricing rules engine with hot-reload capability."""
    
    _instance: "PricingRules | None" = None
    _last_modified: float = 0
    _config: PricingConfig | None = None
    
    def __new__(cls) -> "PricingRules":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        # Only initialize once
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.config_path = Path(settings.PRICING_CONFIG_PATH)
            self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file with validation."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            # Validate with Pydantic
            self._config = PricingConfig(**data)
            self._last_modified = self.config_path.stat().st_mtime
            
        except FileNotFoundError:
            raise RuntimeError(f"Pricing config file not found: {self.config_path}")
        except ValidationError as e:
            raise RuntimeError(f"Invalid pricing configuration: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load pricing config: {e}")
    
    def _should_reload(self) -> bool:
        """Check if config file has been modified."""
        try:
            return self.config_path.stat().st_mtime > self._last_modified
        except FileNotFoundError:
            return False
    
    def reload_if_changed(self) -> bool:
        """Reload config if file has changed. Returns True if reloaded."""
        if self._should_reload():
            self._load_config()
            return True
        return False
    
    @property
    def config(self) -> PricingConfig:
        """Get current configuration, reloading if changed."""
        self.reload_if_changed()
        if self._config is None:
            raise RuntimeError("Pricing configuration not loaded")
        return self._config
    
    def get_factor_weights(self) -> dict[str, float]:
        """Get factor weights as flat dictionary."""
        weights = self.config.factor_weights
        return weights.model_dump()
    
    def get_service_package(self, service_type: str, package_name: str) -> ServicePackage:
        """Get service package configuration."""
        try:
            return self.config.service_packages[service_type][package_name]
        except KeyError:
            raise ValueError(f"Service package not found: {service_type}.{package_name}")
    
    def get_base_rate(self, service_type: str) -> float:
        """Get base rate for service type."""
        # Try to get from service_packages first, fallback to base_rates
        try:
            # Get any package for this service type to get the base_rate
            service_packages = self.config.service_packages.get(service_type, {})
            if service_packages:
                # Return the base_rate of the first package
                first_package = next(iter(service_packages.values()))
                return first_package.base_rate
        except (KeyError, StopIteration):
            pass
        
        # Fallback to base_rates config
        return self.config.base_rates.get(service_type, 1000.0)  # Default 1000 INR/hour
    
    def get_negotiation_limits(self, package_name: str) -> NegotiationLimits:
        """Get negotiation limits (same for all packages in this implementation)."""
        # In a more complex implementation, these could vary by package
        return self.config.negotiation_limits


def get_pricing_rules() -> PricingRules:
    """Get cached pricing rules singleton."""
    return PricingRules()