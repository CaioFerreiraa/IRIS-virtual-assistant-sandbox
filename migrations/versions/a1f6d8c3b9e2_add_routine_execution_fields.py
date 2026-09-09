"""add routine execution fields

Revision ID: a1f6d8c3b9e2
Revises: e4b7c2d9a6f1
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a1f6d8c3b9e2"
down_revision: str | Sequence[str] | None = "e4b7c2d9a6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())

    if "routine" not in table_names:
        op.create_table(
            "routine",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("cron_expression", sa.String(length=100), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=True),
            sa.Column(
                "stop_on_failure",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        routine_columns = {
            column["name"] for column in inspector.get_columns("routine")
        }
        with op.batch_alter_table("routine") as batch_op:
            if "stop_on_failure" not in routine_columns:
                batch_op.add_column(
                    sa.Column(
                        "stop_on_failure",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.true(),
                    )
                )
            if "deleted_at" not in routine_columns:
                batch_op.add_column(
                    sa.Column("deleted_at", sa.DateTime(), nullable=True)
                )

    if "routine_actions" not in table_names:
        op.create_table(
            "routine_actions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("routine_id", sa.Integer(), nullable=False),
            sa.Column("module_id", sa.Integer(), nullable=False),
            sa.Column("execution_order", sa.Integer(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=True),
            sa.Column("argument", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
            sa.ForeignKeyConstraint(["routine_id"], ["routine.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        action_columns = {
            column["name"]
            for column in inspector.get_columns("routine_actions")
        }
        if "argument" not in action_columns:
            with op.batch_alter_table("routine_actions") as batch_op:
                batch_op.add_column(sa.Column("argument", sa.Text(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    if "routine_actions" in table_names:
        action_columns = {
            column["name"]
            for column in inspector.get_columns("routine_actions")
        }
        if "argument" in action_columns:
            with op.batch_alter_table("routine_actions") as batch_op:
                batch_op.drop_column("argument")

    if "routine" in table_names:
        routine_columns = {
            column["name"] for column in inspector.get_columns("routine")
        }
        with op.batch_alter_table("routine") as batch_op:
            if "deleted_at" in routine_columns:
                batch_op.drop_column("deleted_at")
            if "stop_on_failure" in routine_columns:
                batch_op.drop_column("stop_on_failure")
