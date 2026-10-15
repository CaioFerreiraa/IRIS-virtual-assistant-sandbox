"""Permite salvar um campo da resposta HTTP em Vault Key declarada."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a9d7c4b2e6f1"
down_revision: str | Sequence[str] | None = "c8a2f6d4e9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("module_http_requests") as batch_op:
        batch_op.add_column(
            sa.Column(
                "response_vault_json",
                sa.Text(),
                nullable=False,
                server_default="null",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("module_http_requests") as batch_op:
        batch_op.drop_column("response_vault_json")
