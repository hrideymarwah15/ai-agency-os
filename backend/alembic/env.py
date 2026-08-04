"""Alembic async migration environment for AI Agency OS."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.sql.schema import SchemaItem

# Import models so autogenerate sees every table (alembic autogen imports metadata).
import backend.database as _database  # noqa: F401
from backend.config import settings
from backend.database import Base, build_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tables created and managed by langgraph AsyncPostgresSaver.setup(), NOT by
# Alembic — autogen/`alembic check` must never propose dropping or diffing them.
_LANGGRAPH_TABLES = {
    "checkpoints",
    "checkpoint_writes",
    "checkpoint_blobs",
    "checkpoint_migrations",
}


def include_object(
    object: SchemaItem,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    """Skip langgraph-managed checkpointer tables in autogenerate comparisons."""
    return not (type_ == "table" and name in _LANGGRAPH_TABLES)


def get_url() -> str:
    """Prefer DATABASE_URL (tests set it to the test DB), fall back to settings."""
    return os.environ.get("DATABASE_URL") or settings.database_url


def get_async_url() -> str:
    """The configured URL with the asyncpg driver guaranteed (never double-added)."""
    return str(build_database_url(get_url()))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against an async engine built from the configured URL."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=get_async_url(),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
