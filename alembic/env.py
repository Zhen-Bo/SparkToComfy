"""Alembic environment.

The database location comes from two sources, in order: 1.
`config.attributes["url"]` set by the caller (tests use this for a temp file). 2.
`server.database` in `config/app.toml` (used when alembic runs from the CLI).
"""

import asyncio
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app import config as app_config
from app.database import Base

target_metadata = Base.metadata


def url() -> str:
    given = context.config.attributes.get("url")
    if given:
        return given
    path = Path(app_config.ROOT / app_config.SETTINGS.database)
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def _configure(**kwargs) -> None:
    # render_as_batch: SQLite has no full ALTER TABLE, so batch mode keeps later column changes possible.
    context.configure(target_metadata=target_metadata, render_as_batch=True, **kwargs)


def run_offline() -> None:
    _configure(url=url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = async_engine_from_config(
        {"sqlalchemy.url": url()}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
