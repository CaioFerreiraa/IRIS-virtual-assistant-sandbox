"""add explicit module call aliases

Revision ID: a1c9e7d5b2f4
Revises: f2b8a9d4c6e1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a1c9e7d5b2f4"
down_revision: str | Sequence[str] | None = "f2b8a9d4c6e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("modules")}
    if "call_aliases_json" not in columns:
        with op.batch_alter_table("modules") as batch_op:
            batch_op.add_column(
                sa.Column("call_aliases_json", sa.Text(), nullable=False, server_default="[]")
            )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("modules")}
    if "call_aliases_json" in columns:
        with op.batch_alter_table("modules") as batch_op:
            batch_op.drop_column("call_aliases_json")
