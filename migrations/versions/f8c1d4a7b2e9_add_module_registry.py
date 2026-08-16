"""add module registry and variable settings

Revision ID: f8c1d4a7b2e9
Revises: e5f7a9c2d4b1
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f8c1d4a7b2e9"
down_revision: str | Sequence[str] | None = "e5f7a9c2d4b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA defer_foreign_keys=ON")
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_modules")

    table_names = set(sa.inspect(op.get_bind()).get_table_names())
    parent_foreign_key_exists = any(
        foreign_key.get("constrained_columns") == ["parent_module_id"]
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys("modules")
    )
    with op.batch_alter_table(
        "modules",
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.add_column(sa.Column("module_public_key", sa.String(length=120), nullable=True))
        batch_op.add_column(
            sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(sa.Column("validation_error", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("manifest_directory", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("readme_path", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("runtime_type", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("supports_auto_start", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("auto_start_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.execute(
        """
        UPDATE modules
        SET module_public_key = 'legacy.module-' || id
        WHERE module_public_key IS NULL OR trim(module_public_key) = ''
        """
    )

    with op.batch_alter_table(
        "modules",
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.alter_column(
            "module_public_key",
            existing_type=sa.String(length=120),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_modules_module_public_key",
            ["module_public_key"],
        )
        batch_op.create_check_constraint(
            "ck_modules_parent_not_self",
            "parent_module_id IS NULL OR parent_module_id <> id",
        )
        if parent_foreign_key_exists:
            batch_op.drop_constraint(
                "fk_modules_parent_module_id_modules",
                type_="foreignkey",
            )
        batch_op.create_foreign_key(
            "fk_modules_parent_module_id_modules",
            "modules",
            ["parent_module_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    if "module_variable_definitions" not in table_names:
        op.create_table(
            "module_variable_definitions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("module_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=100), nullable=False),
            sa.Column("label", sa.String(length=150), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("type", sa.String(length=30), nullable=False),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_user_editable", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("default_value", sa.Text(), nullable=True),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.ForeignKeyConstraint(
                ["module_id"],
                ["modules.id"],
                name="fk_module_variable_definitions_module_id_modules",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("module_id", "key", name="uq_module_variable_definition"),
        )
    if "module_variable_values" not in table_names:
        op.create_table(
            "module_variable_values",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("variable_definition_id", sa.Integer(), nullable=False),
            sa.Column("value_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["variable_definition_id"],
                ["module_variable_definitions.id"],
                name="fk_module_variable_values_definition_id",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "variable_definition_id",
                name="uq_module_variable_value_definition",
            ),
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA defer_foreign_keys=ON")
    op.drop_table("module_variable_values")
    op.drop_table("module_variable_definitions")

    with op.batch_alter_table(
        "modules",
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_modules_parent_module_id_modules",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_modules_parent_module_id_modules",
            "modules",
            ["parent_module_id"],
            ["id"],
        )
        batch_op.drop_constraint("ck_modules_parent_not_self", type_="check")
        batch_op.drop_constraint("uq_modules_module_public_key", type_="unique")
        batch_op.drop_column("auto_start_enabled")
        batch_op.drop_column("supports_auto_start")
        batch_op.drop_column("runtime_type")
        batch_op.drop_column("readme_path")
        batch_op.drop_column("manifest_directory")
        batch_op.drop_column("validation_error")
        batch_op.drop_column("is_available")
        batch_op.drop_column("module_public_key")
