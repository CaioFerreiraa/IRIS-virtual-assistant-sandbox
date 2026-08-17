"""add module icon

Revision ID: b7e4a1c9d2f6
Revises: f8c1d4a7b2e9
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b7e4a1c9d2f6"
down_revision: str | Sequence[str] | None = "f8c1d4a7b2e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("modules") as batch_op:
        batch_op.add_column(
            sa.Column(
                "icon",
                sa.String(length=100),
                nullable=False,
                server_default="extension",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("modules") as batch_op:
        batch_op.drop_column("icon")
