"""add general settings

Revision ID: a6c8e2f4b1d3
Revises: e4b7c2d9a6f1
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a6c8e2f4b1d3"
down_revision: str | Sequence[str] | None = "e4b7c2d9a6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "general_settings" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "general_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "background_execution_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    if "general_settings" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("general_settings")
