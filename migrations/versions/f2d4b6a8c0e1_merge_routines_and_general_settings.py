"""merge routines and general settings branches

Revision ID: f2d4b6a8c0e1
Revises: a1f6d8c3b9e2, c7d9e1a3f5b2
Create Date: 2026-09-10
"""

from collections.abc import Sequence


revision: str = "f2d4b6a8c0e1"
down_revision: str | Sequence[str] | None = (
    "a1f6d8c3b9e2",
    "c7d9e1a3f5b2",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
