"""track HTTP request customization

Revision ID: e4b7c2d9a6f1
Revises: d9f2a6c4e1b8
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e4b7c2d9a6f1"
down_revision: str | Sequence[str] | None = "d9f2a6c4e1b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("module_http_requests") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_customized",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("module_http_requests") as batch_op:
        batch_op.drop_column("is_customized")
