"""Create the job table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_job"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("workflow_id", sa.Text(), nullable=False),
        sa.Column("prompt_id", sa.Text(), nullable=False),
        sa.Column("params", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("images", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("job_pkey")),
        sa.UniqueConstraint("prompt_id", name=op.f("job_prompt_id_key")),
        sqlite_autoincrement=True,
    )


def downgrade() -> None:
    op.drop_table("job")
