"""initial research_results table

Revision ID: 0001
Revises:
Create Date: 2026-06-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSONB on Postgres, generic JSON elsewhere.
_json = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "research_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("result", _json, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_research_results_job_id", "research_results", ["job_id"], unique=True)
    op.create_index("ix_research_results_status", "research_results", ["status"])


def downgrade() -> None:
    op.drop_index("ix_research_results_status", table_name="research_results")
    op.drop_index("ix_research_results_job_id", table_name="research_results")
    op.drop_table("research_results")
