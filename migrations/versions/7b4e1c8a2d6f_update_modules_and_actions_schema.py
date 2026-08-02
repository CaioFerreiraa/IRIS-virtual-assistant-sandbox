"""update modules and actions schema

Revision ID: 7b4e1c8a2d6f
Revises: 108d3039c98a
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b4e1c8a2d6f"
down_revision: Union[str, Sequence[str], None] = "108d3039c98a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("modules") as batch_op:
        batch_op.add_column(sa.Column("call_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("custom_call_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("created_date", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("edited_date", sa.DateTime(), nullable=True))

    op.execute(
        """
        UPDATE modules
        SET
            call_name = name,
            created_date = created_at,
            edited_date = created_at
        """
    )

    with op.batch_alter_table("modules") as batch_op:
        batch_op.alter_column("call_name", existing_type=sa.String(length=100), nullable=False)
        batch_op.drop_column("active")
        batch_op.drop_column("created_at")

    with op.batch_alter_table("actions") as batch_op:
        batch_op.add_column(sa.Column("call_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("custom_call_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("id_module", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("created_date", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("edited_date", sa.DateTime(), nullable=True))

    op.execute(
        """
        UPDATE actions
        SET
            call_name = action_key,
            id_module = module_id,
            created_date = created_at,
            edited_date = created_at
        """
    )

    with op.batch_alter_table("actions") as batch_op:
        batch_op.alter_column("call_name", existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column("id_module", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("module_id")
        batch_op.drop_column("action_key")
        batch_op.drop_column("active")
        batch_op.drop_column("created_at")
        batch_op.create_foreign_key("fk_actions_id_module_modules", "modules", ["id_module"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("actions") as batch_op:
        batch_op.add_column(sa.Column("module_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("action_key", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("active", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))

    op.execute(
        """
        UPDATE actions
        SET
            module_id = id_module,
            action_key = call_name,
            active = 1,
            created_at = created_date
        """
    )

    with op.batch_alter_table("actions") as batch_op:
        batch_op.alter_column("module_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("action_key", existing_type=sa.String(length=100), nullable=False)
        batch_op.drop_constraint("fk_actions_id_module_modules", type_="foreignkey")
        batch_op.drop_column("id_module")
        batch_op.drop_column("call_name")
        batch_op.drop_column("custom_call_name")
        batch_op.drop_column("created_date")
        batch_op.drop_column("edited_date")
        batch_op.create_foreign_key("fk_actions_module_id_modules", "modules", ["module_id"], ["id"])

    with op.batch_alter_table("modules") as batch_op:
        batch_op.add_column(sa.Column("active", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))

    op.execute(
        """
        UPDATE modules
        SET
            active = 1,
            created_at = created_date
        """
    )

    with op.batch_alter_table("modules") as batch_op:
        batch_op.drop_column("call_name")
        batch_op.drop_column("custom_call_name")
        batch_op.drop_column("created_date")
        batch_op.drop_column("edited_date")
