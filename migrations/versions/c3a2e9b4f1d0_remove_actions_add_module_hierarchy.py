"""remove actions and add module hierarchy

Revision ID: c3a2e9b4f1d0
Revises: 7b4e1c8a2d6f
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a2e9b4f1d0"
down_revision: Union[str, Sequence[str], None] = "7b4e1c8a2d6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("modules") as batch_op:
        batch_op.add_column(sa.Column("parent_module_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_modules_parent_module_id_modules",
            "modules",
            ["parent_module_id"],
            ["id"],
        )

    op.execute(
        """
        INSERT INTO modules (
            name,
            call_name,
            custom_call_name,
            description,
            parent_module_id,
            created_date,
            edited_date
        )
        SELECT
            actions.name,
            actions.call_name,
            actions.custom_call_name,
            actions.description,
            actions.id_module,
            actions.created_date,
            actions.edited_date
        FROM actions
        WHERE NOT EXISTS (
            SELECT 1
            FROM modules
            WHERE modules.parent_module_id = actions.id_module
                AND modules.call_name = actions.call_name
        )
        """
    )

    with op.batch_alter_table("logs") as batch_op:
        batch_op.add_column(sa.Column("module_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("routine_actions") as batch_op:
        batch_op.add_column(sa.Column("module_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE logs
        SET module_id = (
            SELECT modules.id
            FROM modules
            JOIN actions
                ON modules.parent_module_id = actions.id_module
                AND modules.call_name = actions.call_name
            WHERE actions.id = logs.action_id
            LIMIT 1
        )
        WHERE module_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE routine_actions
        SET module_id = (
            SELECT modules.id
            FROM modules
            JOIN actions
                ON modules.parent_module_id = actions.id_module
                AND modules.call_name = actions.call_name
            WHERE actions.id = routine_actions.action_id
            LIMIT 1
        )
        WHERE module_id IS NULL
        """
    )

    with op.batch_alter_table("logs") as batch_op:
        batch_op.alter_column("module_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("action_id")
        batch_op.create_foreign_key(
            "fk_logs_module_id_modules",
            "modules",
            ["module_id"],
            ["id"],
        )

    with op.batch_alter_table("routine_actions") as batch_op:
        batch_op.alter_column("module_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("action_id")
        batch_op.create_foreign_key(
            "fk_routine_actions_module_id_modules",
            "modules",
            ["module_id"],
            ["id"],
        )

    op.drop_table("actions")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("call_name", sa.String(length=100), nullable=False),
        sa.Column("custom_call_name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id_module", sa.Integer(), nullable=False),
        sa.Column("created_date", sa.DateTime(), nullable=True),
        sa.Column("edited_date", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["id_module"], ["modules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        INSERT INTO actions (
            id,
            name,
            call_name,
            custom_call_name,
            description,
            id_module,
            created_date,
            edited_date
        )
        SELECT
            id,
            name,
            call_name,
            custom_call_name,
            description,
            parent_module_id,
            created_date,
            edited_date
        FROM modules
        WHERE parent_module_id IS NOT NULL
        """
    )

    with op.batch_alter_table("logs") as batch_op:
        batch_op.add_column(sa.Column("action_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("routine_actions") as batch_op:
        batch_op.add_column(sa.Column("action_id", sa.Integer(), nullable=True))

    op.execute("UPDATE logs SET action_id = module_id WHERE action_id IS NULL")
    op.execute(
        """
        UPDATE routine_actions
        SET action_id = module_id
        WHERE action_id IS NULL
        """
    )

    with op.batch_alter_table("logs") as batch_op:
        batch_op.alter_column("action_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint("fk_logs_module_id_modules", type_="foreignkey")
        batch_op.drop_column("module_id")
        batch_op.create_foreign_key(
            "fk_logs_action_id_actions",
            "actions",
            ["action_id"],
            ["id"],
        )

    with op.batch_alter_table("routine_actions") as batch_op:
        batch_op.alter_column("action_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint(
            "fk_routine_actions_module_id_modules",
            type_="foreignkey",
        )
        batch_op.drop_column("module_id")
        batch_op.create_foreign_key(
            "fk_routine_actions_action_id_actions",
            "actions",
            ["action_id"],
            ["id"],
        )

    with op.batch_alter_table("modules") as batch_op:
        batch_op.drop_constraint(
            "fk_modules_parent_module_id_modules",
            type_="foreignkey",
        )
        batch_op.drop_column("parent_module_id")
