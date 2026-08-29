"""Data access for the job table.

lifespan builds the engine (see app/runtime.py), not import time, so importing app.database never touches the disk and tests need not care about import order. alembic/ owns the schema.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, NullPool, Text, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.settings import ROOT

# Max rows one history listing returns.
# The frontend reads it from the X-History-Limit header on GET /v1/history instead of keeping its own copy.
HISTORY_LIMIT = 50

ALEMBIC_INI = ROOT / "alembic.ini"

NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class JobRow(Base):
    __tablename__ = "job"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(Text)
    workflow_id: Mapped[str] = mapped_column(Text)
    prompt_id: Mapped[str] = mapped_column(Text, unique=True)
    params: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    images: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    finished_at: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[str | None] = mapped_column(Text)


@dataclass(frozen=True, slots=True)
class JobSubmission:
    prompt_id: str
    session_id: str
    workflow_id: str
    params: dict[str, object]
    created_at: str


def now() -> str:
    return datetime.now(UTC).isoformat()


def db_url(path: str | Path) -> str:
    return f"sqlite+aiosqlite:///{Path(path).as_posix()}"


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.url = db_url(self.path)
        self.engine = create_async_engine(self.url, poolclass=NullPool)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def migrate(self) -> None:
        """Bring the schema to head. The alembic API is sync, so run it in a thread."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        cfg = Config(str(ALEMBIC_INI))
        cfg.attributes["url"] = self.url
        await asyncio.to_thread(command.upgrade, cfg, "head")
        async with self.engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")

    async def aclose(self) -> None:
        await self.engine.dispose()

    # --- writes ---

    async def insert_finished(
        self,
        job: JobSubmission,
        status: str,
        *,
        images: list[dict] | None = None,
        error: str | None = None,
    ) -> None:
        """One call for both done and failed, so the row shape is defined in one place."""
        async with self.session.begin() as session:
            session.add(
                JobRow(
                    session_id=job.session_id,
                    workflow_id=job.workflow_id,
                    prompt_id=job.prompt_id,
                    params=json.dumps(job.params),
                    status=status,
                    error=error,
                    images=None if images is None else json.dumps(images),
                    created_at=job.created_at,
                    finished_at=now(),
                )
            )

    # --- reads ---

    async def get_job(self, session_id: str, prompt_id: str) -> dict | None:
        """The finished record of one job of this session: status, image refs, error text."""
        async with self.session() as session:
            row = await session.scalar(
                select(JobRow).where(
                    JobRow.session_id == session_id,
                    JobRow.prompt_id == prompt_id,
                    JobRow.deleted_at.is_(None),
                )
            )
        if row is None:
            return None
        return {
            "status": row.status,
            "images": json.loads(row.images or "[]"),
            "error": row.error,
        }

    async def has_done(self, session_id: str, prompt_id: str) -> bool:
        async with self.session() as session:
            found = await session.scalar(
                select(JobRow.id).where(
                    JobRow.session_id == session_id,
                    JobRow.prompt_id == prompt_id,
                    JobRow.status == "done",
                )
            )
        return found is not None

    async def list_jobs(self, session_id: str) -> list[dict]:
        async with self.session() as session:
            rows = (
                await session.scalars(
                    select(JobRow)
                    .where(
                        JobRow.session_id == session_id,
                        JobRow.status == "done",
                        JobRow.deleted_at.is_(None),
                    )
                    .order_by(JobRow.id.desc())
                    .limit(HISTORY_LIMIT)
                )
            ).all()
        return [
            {
                "workflow_id": row.workflow_id,
                "prompt_id": row.prompt_id,
                "params": json.loads(row.params),
                "images": json.loads(row.images or "[]"),
                "created_at": row.created_at,
                "finished_at": row.finished_at,
            }
            for row in rows
        ]

    async def get_image_ref(self, prompt_id: str, index: int) -> dict | None:
        async with self.session() as session:
            raw = await session.scalar(
                select(JobRow.images).where(
                    JobRow.prompt_id == prompt_id,
                    JobRow.status == "done",
                    JobRow.deleted_at.is_(None),
                )
            )
        if raw is None:
            return None
        images = json.loads(raw)
        return images[index] if index < len(images) else None

    # --- soft delete ---

    async def clear_history(self, session_id: str) -> None:
        async with self.session.begin() as session:
            await session.execute(
                update(JobRow)
                .where(JobRow.session_id == session_id, JobRow.deleted_at.is_(None))
                .values(deleted_at=now())
            )

    async def delete_prompts(self, session_id: str, prompt_ids: list[str]) -> bool:
        ids = list(dict.fromkeys(prompt_ids))
        async with self.session.begin() as session:
            found = await session.scalar(
                select(func.count())
                .select_from(JobRow)
                .where(JobRow.session_id == session_id, JobRow.prompt_id.in_(ids))
            )
            if found != len(ids):
                return False
            await session.execute(
                update(JobRow)
                .where(
                    JobRow.session_id == session_id,
                    JobRow.deleted_at.is_(None),
                    JobRow.prompt_id.in_(ids),
                )
                .values(deleted_at=now())
            )
        return True
