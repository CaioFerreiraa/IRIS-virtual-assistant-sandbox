"""Permite Vault Keys cadastradas sem valor inicial."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e3a6c9f1d2b4"
down_revision: str | Sequence[str] | None = "a9d7c4b2e6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vault_keys") as batch_op:
        batch_op.alter_column(
            "encrypted_value",
            existing_type=sa.Text(),
            existing_nullable=False,
            nullable=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    missing_values = connection.execute(
        sa.text("SELECT COUNT(*) FROM vault_keys WHERE encrypted_value IS NULL")
    ).scalar_one()
    if missing_values:
        raise RuntimeError(
            "Não é possível voltar a migration com Vault Keys sem valor. "
            "Cadastre valores ou exclua essas chaves antes do downgrade."
        )
    with op.batch_alter_table("vault_keys") as batch_op:
        batch_op.alter_column(
            "encrypted_value",
            existing_type=sa.Text(),
            existing_nullable=True,
            nullable=False,
        )
