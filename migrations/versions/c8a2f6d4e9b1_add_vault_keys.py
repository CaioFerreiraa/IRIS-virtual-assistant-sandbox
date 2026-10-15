"""Adiciona Vault Keys locais e declarações dos módulos."""

from alembic import op
import sqlalchemy as sa


revision = "c8a2f6d4e9b1"
down_revision = "b4e6f8a0c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vault_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("allow_iris_update", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_date", sa.DateTime(), nullable=False),
        sa.Column("edited_date", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_vault_keys_name"),
    )
    op.add_column("modules", sa.Column("vault_keys_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("modules") as batch_op:
        batch_op.drop_column("vault_keys_json")
    op.drop_table("vault_keys")
