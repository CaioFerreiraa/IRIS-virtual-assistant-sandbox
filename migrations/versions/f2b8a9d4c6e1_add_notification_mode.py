"""add exclusive notification channel

Revision ID: f2b8a9d4c6e1
Revises: c7d9e1a3f5b2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f2b8a9d4c6e1"
down_revision: str | Sequence[str] | None = "c7d9e1a3f5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("general_settings")}
    if "notification_mode" not in columns:
        with op.batch_alter_table("general_settings") as batch_op:
            batch_op.add_column(
                sa.Column("notification_mode", sa.String(16), nullable=False, server_default="iris")
            )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("general_settings")}
    if "notification_mode" in columns:
        with op.batch_alter_table("general_settings") as batch_op:
            batch_op.drop_column("notification_mode")
