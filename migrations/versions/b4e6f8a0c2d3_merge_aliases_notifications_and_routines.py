"""merge aliases, notifications and routines branches

Revision ID: b4e6f8a0c2d3
Revises: a1c9e7d5b2f4, f2d4b6a8c0e1
Create Date: 2026-10-04
"""

from collections.abc import Sequence


revision: str = "b4e6f8a0c2d3"
down_revision: str | Sequence[str] | None = (
    "a1c9e7d5b2f4",
    "f2d4b6a8c0e1",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
