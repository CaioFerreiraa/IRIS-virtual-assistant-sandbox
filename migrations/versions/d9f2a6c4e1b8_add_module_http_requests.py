"""add module HTTP requests

Revision ID: d9f2a6c4e1b8
Revises: b7e4a1c9d2f6
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d9f2a6c4e1b8"
down_revision: str | Sequence[str] | None = "b7e4a1c9d2f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "module_http_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "argument_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("argument", sa.Text(), nullable=True),
        sa.Column(
            "params_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "authorization_json",
            sa.Text(),
            nullable=False,
            server_default='{"type":"none"}',
        ),
        sa.Column(
            "headers_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "body_json",
            sa.Text(),
            nullable=False,
            server_default='{"mode":"none","content":""}',
        ),
        sa.Column(
            "scripts_json",
            sa.Text(),
            nullable=False,
            server_default='{"pre_request":"","post_response":""}',
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["modules.id"],
            name="fk_module_http_requests_module_id_modules",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "module_id",
            name="uq_module_http_requests_module_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("module_http_requests")
