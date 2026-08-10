---
phase: 03-sales
plan: 01
summary: Build the deterministic Pricing Engine — the foundation for all sales pricing decisions. Config-driven YAML (hot-reloadable like opportunities rules), computes recommended/min/target prices, max discount, profit margin, and negotiation limits from 8 weighted factors. Mirrors the Phase 02.2 opportunities rule engine pattern: PricingRules singleton with file watcher, PricingEngine stateless computation, outbox worker for async jobs, owner-editable dashboard with live preview. Every calculation audited. This plan is independent and runs in Wave 1.
completed: 2026-08-10
---

# Phase 03 Sales Plan 01: Pricing Engine Summary

## Overview

Successfully built the deterministic Pricing Engine — the foundation for all sales pricing decisions. The system features config-driven YAML pricing (hot-reloadable like opportunities rules), computes recommended/min/target prices, max discount, profit margin, and negotiation limits from 8 weighted factors. Mirrors the Phase 02.2 opportunities rule engine pattern: PricingRules singleton with file watcher, PricingEngine stateless computation, outbox worker for async jobs, owner-editable dashboard with live preview. Every calculation audited.

## Accomplishments

### Task 1: Pricing config YAML + Rules singleton with hot-reload
- Created `backend/config/pricing.yaml` with all pricing configuration per SPEC-003 §5.3 and CONTEXT.md Decisions §2
- Created `backend/services/pricing/rules.py` with PricingRules singleton (mirroring OpportunitiesRules pattern)
- Updated `backend/config.py` to add PRICING_CONFIG_PATH setting
- Created `backend/services/pricing/__init__.py` to make it a package
- Verification: pricing.yaml exists with all required sections; PricingRules singleton loads, validates, hot-reloads on file change

### Task 2: Pricing engine computation + database models + alembic migration
- Created `backend/services/pricing/engine.py` with deterministic PricingEngine
- Extended `backend/database.py` with PricingRun and PricingRuleVersion models for audit trail
- Created alembic migration 0006_pricing_engine.py with both tables and indexes
- Verification: PricingEngine.compute() returns deterministic PricingOutput with all fields; Migration creates pricing_runs and pricing_rule_versions tables; All calculations use Decimal for financial precision (no float)

### Task 3: Pricing API routes + dashboard page + outbox worker + tests
- Created `backend/services/pricing/worker.py` (mirroring opportunities/worker.py)
- Created `backend/api/pricing.py` with owner-guarded routes
- Created `backend/templates/pricing.html` (extends base.html)
- Updated `backend/main.py` to include pricing router and start pricing_worker in lifespan
- Created tests: test_pricing_rules.py, test_pricing_engine.py, test_pricing_api.py
- Verification: All pricing tests pass; API routes return correct PricingOutput; dashboard page renders with live preview; worker processes outbox events; audit records created

## Key Features Implemented

1. **Hot-reloadable Configuration**: Pricing rules stored in YAML file with file watcher for automatic reload
2. **Deterministic Calculation**: PricingEngine computes prices using 8 weighted factors with Decimal precision
3. **Audit Trail**: Complete audit trail of all pricing calculations stored in database
4. **Owner-Guarded API**: Secure API endpoints for calculating prices, managing rules, and viewing audit trail
5. **Interactive Dashboard**: Live pricing rules editor with real-time price calculator and audit trail view
6. **Async Processing**: Outbox worker for handling pricing calculation requests asynchronously
7. **Extensible Design**: Follows the same pattern as the opportunities rule engine for consistency

## Files Modified

### New Files Created:
- `backend/config/pricing.yaml` - Pricing configuration YAML
- `backend/services/pricing/__init__.py` - Package initializer
- `backend/services/pricing/rules.py` - PricingRules singleton with hot-reload
- `backend/services/pricing/engine.py` - Deterministic PricingEngine
- `backend/services/pricing/worker.py` - Outbox worker for pricing calculations
- `backend/api/pricing.py` - Owner-guarded pricing API routes
- `backend/templates/pricing.html` - Pricing dashboard template
- `tests/test_pricing_rules.py` - Pricing rules unit tests
- `tests/test_pricing_engine.py` - Pricing engine unit tests
- `tests/test_pricing_api.py` - Pricing API integration tests

### Existing Files Modified:
- `backend/config.py` - Added PRICING_CONFIG_PATH setting
- `backend/database.py` - Added PricingRun and PricingRuleVersion models
- `backend/main.py` - Added pricing router and worker to lifespan

## Technical Details

### Pricing Calculation Algorithm:
1. Load package configuration from PricingRules
2. Base price = sum(scope_matrix line_items.hours × base_rate × complexity_multiplier)
3. Apply factor weights: each factor contributes (factor_value × weight) to multiplier
4. Apply industry and size multipliers from settings
5. recommended_price = round(base_price × combined_multiplier)
6. minimum_price = round(recommended_price × (1 - max_discount_pct/100))
7. target_price = recommended_price (configurable offset)
8. profit_margin_pct = ((recommended_price - cost_estimate) / recommended_price) × 100
9. negotiation_limits from package config

### Audit Trail:
- Every pricing calculation creates a PricingRun record with:
  - Correlation ID for tracking
  - Input parameters and output results stored as JSON
  - Package and service type for categorization
  - Status (PENDING/COMPLETED/FAILED)
  - Timestamp

### Configuration Hot-Reload:
- File system watcher detects changes to pricing.yaml
- Automatic re-validation with Pydantic models
- Seamless transition to new configuration without service restart

## Verification Results

All verification criteria from the plan have been met:

- [x] Pricing engine computes recommended/min/target prices, max discount, margin, negotiation limits from 8 weighted factors
- [x] Config is YAML-driven, hot-reloadable, owner-editable via dashboard with live preview
- [x] Service packages from existing service_catalog priced with scope matrices
- [x] Dynamic adjustments (bundles, long-term, referral) as config toggles
- [x] All calculations audited with correlation_id; Decimal used for financial precision
- [x] Owner can view/edit pricing rules and see audit trail in dashboard

## Dependencies

This plan depends on:
- Existing service catalog in backend/config.py
- Existing audit system for recording pricing calculations
- Existing outbox pattern from opportunities and discovery workers
- Existing authentication system (get_current_owner dependency)
- Existing database initialization and session management

## Future Work

This foundation enables future sales functionality including:
- Opportunity-to-quote conversion with automated pricing
- Customer-specific pricing rules and discounts
- Price approval workflows for high-value deals
- Integration with contract generation and e-signature systems
- Sales performance analytics and reporting