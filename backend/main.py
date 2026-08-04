"""FastAPI application entry point for AI Agency OS (D-17 server-rendered UI)."""

from __future__ import annotations

import asyncio
import re
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend import database

if TYPE_CHECKING:
    # Typing-only: loguru does not export Record at runtime.
    from loguru import Record

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── D-18: secret-redacting loguru sink ────────────────────────────────────
# Scrub sensitive values (*key/*token/*secret/*password/*cookie and
# X-Goog-Api-Key header values) from every log line before it is emitted.
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b((?:api[-_]?key|key|token|secret|password|cookie|x-goog-api-key)"
    r"[\"'=:\s]+)([^\"'\s,;]+)"
)


def redact_secrets(record: Record) -> bool:
    """Scrub secret values from a log record's message; always keep the record."""
    record["message"] = _SECRET_VALUE_RE.sub(r"\1[REDACTED]", record["message"])
    return True


def _configure_logging() -> None:
    """Install the D-18 redaction sink as the sole loguru sink."""
    logger.remove()
    logger.add(sys.stderr, filter=redact_secrets)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Full app lifecycle: init DB → migrate → checkpointer setup → shutdown."""
    await database.init_db()
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "alembic"))
    # env.py runs its own asyncio.run() — must be off the event loop (Pitfall 3).
    await asyncio.to_thread(command.upgrade, cfg, "head")
    # LangGraph durable checkpoints — postgresql:// DSN (psycopg, not asyncpg).
    # from_conn_string is an async context manager; setup() must run once (Pitfall 3).
    async with AsyncPostgresSaver.from_conn_string(database.postgres_dsn()) as checkpointer:
        await checkpointer.setup()
    yield
    await database.close_db()


app = FastAPI(title="AI Agency OS", lifespan=lifespan)

_configure_logging()


@app.get("/health")
async def health() -> JSONResponse:
    """Liveness probe: report ok only when the database answers a SELECT 1."""
    if database.async_session_maker is None:
        return JSONResponse(status_code=503, content={"status": "error"})
    try:
        async with database.async_session_maker() as session:
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        logger.exception("Health check failed — database unreachable")
        return JSONResponse(status_code=503, content={"status": "error"})
    return JSONResponse(status_code=200, content={"status": "ok"})
