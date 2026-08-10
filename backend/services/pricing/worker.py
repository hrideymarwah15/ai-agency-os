"""Outbox worker for pricing calculations (pricing.calculate events).

Drains ``pricing.calculate`` events one at a time, calls :func:`PricingEngine.compute`,
and stores the result in PricingRun. Mirrors the pattern used by the opportunity and audit workers.
"""

import asyncio
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import select

from backend import database
from backend.database import OutboxEvent, PricingRun, utc_now

from .engine import PricingEngine, PricingInput

_PRICING_TOPIC = "pricing.calculate"
_POLL_INTERVAL_SECONDS = 5.0
_MAX_ERROR_LENGTH = 1000


async def pricing_worker(*, poll_interval: float = _POLL_INTERVAL_SECONDS) -> None:
    """Drain ``pricing.calculate`` events → compute pricing → store audit trail."""
    while True:
        try:
            await _process_one()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 – ensure loop continues on errors
            logger.exception("pricing worker iteration failed")
        await asyncio.sleep(poll_interval)


async def _process_one() -> bool:
    """Process one pending pricing.calculate event.
    
    Returns True if an event was processed, False if no pending events.
    """
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    
    async with session_maker() as session:
        # Find oldest pending pricing.calculate event
        result = await session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.topic == _PRICING_TOPIC,
                OutboxEvent.status == "PENDING",
            )
            .order_by(OutboxEvent.created_at)
            .limit(1)
        )
        event = result.scalars().first()
        if event is None:
            return False
        
        # Mark as in progress
        event.status = "IN_PROGRESS"
        event.attempts += 1
        await session.commit()
        
        try:
            # Parse input from event payload
            payload = event.payload
            pricing_input = PricingInput(
                hours=float(payload["hours"]),
                complexity=float(payload["complexity"]),
                market_rate=float(payload["market_rate"]),
                competition=float(payload["competition"]),
                industry=payload["industry"],
                size=payload["size"],
                expected_roi=float(payload["expected_roi"]),
                historical_close_rate=float(payload["historical_close_rate"]),
                package_name=payload["package_name"],
                service_type=payload["service_type"]
            )
            
            # Compute pricing
            engine = PricingEngine()
            pricing_output = engine.compute(pricing_input)
            
            # Create pricing run record
            pricing_run = PricingRun(
                correlation_id=payload.get("correlation_id", str(uuid4())),
                input_json=payload,
                output_json=pricing_output.model_dump(),
                package_name=pricing_input.package_name,
                service_type=pricing_input.service_type,
                status="COMPLETED"
            )
            session.add(pricing_run)
            
            # Mark event as done
            event.status = "DONE"
            event.processed_at = utc_now()
            await session.commit()
            
            return True
            
        except Exception as exc:  # noqa: BLE001
            # Mark event as failed
            event.status = "FAILED"
            event.last_error = str(exc)[:_MAX_ERROR_LENGTH]
            event.processed_at = utc_now()
            await session.commit()
            logger.error("pricing event {} failed: {}", event.id, exc)
            return True