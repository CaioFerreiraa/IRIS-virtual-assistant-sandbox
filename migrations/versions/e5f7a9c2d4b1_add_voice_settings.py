"""add voice settings

Revision ID: e5f7a9c2d4b1
Revises: c3a2e9b4f1d0
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e5f7a9c2d4b1"
down_revision: str | Sequence[str] | None = "c3a2e9b4f1d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "voice_settings" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "voice_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="basic"),
        sa.Column("language", sa.String(length=10), nullable=False, server_default="pt"),
        sa.Column("model_size", sa.String(length=100), nullable=False, server_default="small"),
        sa.Column("realtime_model_size", sa.String(length=100), nullable=False, server_default="tiny"),
        sa.Column("device", sa.String(length=20), nullable=False, server_default="cpu"),
        sa.Column("compute_type", sa.String(length=30), nullable=False, server_default="int8"),
        sa.Column("input_device_index", sa.Integer(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=False, server_default="16000"),
        sa.Column("audio_threshold", sa.Float(), nullable=False, server_default="0.025"),
        sa.Column("silence_duration", sa.Float(), nullable=False, server_default="1.2"),
        sa.Column("min_recording_duration", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("realtime_processing_pause", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("beam_size", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("realtime_beam_size", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("realtime_batch_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vad_filter", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("silero_sensitivity", sa.Float(), nullable=False, server_default="0.4"),
        sa.Column("webrtc_sensitivity", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("proper_names", sa.Text(), nullable=False, server_default=""),
        sa.Column("context", sa.Text(), nullable=False, server_default=""),
        sa.Column("hotwords", sa.Text(), nullable=False, server_default=""),
        sa.Column("condition_on_previous_text", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    if "voice_settings" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("voice_settings")
