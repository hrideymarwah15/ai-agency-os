"""Pricing routes — owner-guarded DB access proving the pricing engine skeleton."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path as FastAPIPath, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID

from backend import config
from backend.auth.owner import get_current_owner
from backend.auth.session import clear_flash, read_flash, set_flash
from backend.database import get_db, PricingRun
from backend.services.pricing.engine import PricingEngine, PricingInput
from backend.services.audit import AuditService

router = APIRouter(prefix="/pricing", tags=["pricing"])

templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"
))


@router.post("/calculate")
async def calculate_pricing(
    request: Request,
    pricing_input: PricingInput,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Calculate pricing for given parameters.
    
    Owner-guarded endpoint that computes pricing, stores audit trail,
    and returns the pricing output.
    """
    # Compute pricing
    engine = PricingEngine()
    pricing_output = engine.compute(pricing_input)
    
    # Generate correlation ID for audit trail
    correlation_id = str(UUID(int=datetime.now(UTC).timestamp()))
    
    # Store pricing run for audit trail
    pricing_run = PricingRun(
        correlation_id=correlation_id,
        input_json=pricing_input.model_dump(),
        output_json=pricing_output.model_dump(),
        package_name=pricing_input.package_name,
        service_type=pricing_input.service_type,
        status="COMPLETED"
    )
    session.add(pricing_run)
    await session.commit()
    
    # Audit the pricing calculation
    await AuditService.record(
        session,
        correlation_id=correlation_id,
        action="pricing.calculate",
        actor=_owner,
        details={
            "package_name": pricing_input.package_name,
            "service_type": pricing_input.service_type,
            "recommended_price": pricing_output.recommended_price
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=pricing_output.model_dump()
    )


@router.get("/rules")
async def get_pricing_rules(
    request: Request,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Get current pricing configuration.
    
    Returns the parsed YAML pricing configuration.
    """
    from backend.services.pricing.rules import get_pricing_rules
    pricing_rules = get_pricing_rules()
    config_data = pricing_rules.config.model_dump()
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=config_data
    )


@router.put("/rules/{rule_id:path}")
async def update_pricing_rule(
    request: Request,
    rule_id: str = FastAPIPath(..., description="YAML path to the rule to update, e.g. 'factor_weights/hours'"),
    update_data: dict[str, Any] = None,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Update a specific pricing rule.
    
    Note: This is a simplified implementation. In a full implementation,
    this would load the YAML, update the specific field, save it,
    trigger hot-reload, and create a version snapshot.
    """
    # For now, we'll return a placeholder response
    # A full implementation would:
    # 1. Load the current YAML file
    # 2. Navigate to the rule_id path and update the value
    # 3. Save the YAML file (triggering hot-reload via file watcher)
    # 4. Create a PricingRuleVersion snapshot
    # 5. Audit the change
    
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": "Rule updates not yet implemented"}
    )


@router.get("/runs")
async def get_pricing_runs(
    request: Request,
    _owner: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    """Get paginated list of pricing runs for audit trail.
    
    Returns recent pricing calculations with their inputs and outputs.
    """
    result = await session.execute(
        select(PricingRun)
        .order_by(desc(PricingRun.created_at))
        .limit(limit)
        .offset(offset)
    )
    runs = result.scalars().all()
    
    # Convert to dict for JSON response
    runs_data = [
        {
            "id": str(run.id),
            "correlation_id": run.correlation_id,
            "package_name": run.package_name,
            "service_type": run.service_type,
            "status": run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "input_summary": {
                "hours": run.input_json.get("hours"),
                "package_name": run.input_json.get("package_name"),
                "service_type": run.input_json.get("service_type")
            } if run.input_json else None,
            "output_summary": {
                "recommended_price": run.output_json.get("recommended_price"),
                "profit_margin_pct": run.output_json.get("profit_margin_pct")
            } if run.output_json else None
        }
        for run in runs
    ]
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "runs": runs_data,
            "limit": limit,
            "offset": offset,
            "count": len(runs_data)
        }
    )