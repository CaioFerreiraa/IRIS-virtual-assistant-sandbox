"""add listening overlay setting

Revision ID: c7d9e1a3f5b2
Revises: a6c8e2f4b1d3
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c7d9e1a3f5b2"
down_revision: str | Sequence[str] | None = "a6c8e2f4b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("general_settings")
    }
    if "listening_overlay_enabled" in columns:
        return
    with op.batch_alter_table("general_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "listening_overlay_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("general_settings")
    }
    if "listening_overlay_enabled" not in columns:
        return
    with op.batch_alter_table("general_settings") as batch_op:
        batch_op.drop_column("listening_overlay_enabled")
