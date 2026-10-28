"""stage session updates for explicit review

Revision ID: 20261007_0005
Revises: 20260930_0004
Create Date: 2026-10-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261007_0005"
down_revision = "20260930_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_update_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("campaign_id", sa.String(length=128), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("default_tags", sa.JSON(), nullable=False),
        sa.Column("decisions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("session_log_decision", sa.String(length=32), nullable=False),
        sa.Column("session_log_document_id", sa.Integer(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_session_update_drafts_campaign_id",
        "session_update_drafts",
        ["campaign_id"],
    )
    op.create_index("ix_session_update_drafts_id", "session_update_drafts", ["id"])
    op.create_index(
        "ix_session_update_drafts_source_hash",
        "session_update_drafts",
        ["source_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_session_update_drafts_source_hash", table_name="session_update_drafts"
    )
    op.drop_index(
        "ix_session_update_drafts_campaign_id", table_name="session_update_drafts"
    )
    op.drop_index("ix_session_update_drafts_id", table_name="session_update_drafts")
    op.drop_table("session_update_drafts")
