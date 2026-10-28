"""add optimistic revisions to saved contexts

Revision ID: 20260930_0004
Revises: 20260411_0003
Create Date: 2026-09-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260930_0004"
down_revision = "20260411_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contexts",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("contexts", "revision")
