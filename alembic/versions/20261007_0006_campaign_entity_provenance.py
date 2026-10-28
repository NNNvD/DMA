"""record reviewed candidate provenance on promoted campaign entities

Revision ID: 20261007_0006
Revises: 20261007_0005
Create Date: 2026-10-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261007_0006"
down_revision = "20261007_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_entity_provenance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("candidate_type", sa.String(length=32), nullable=False),
        sa.Column("reviewer", sa.String(length=255), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=False),
        sa.Column("candidate_payload", sa.JSON(), nullable=False),
        sa.Column("entity_stable_key", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["draft_id"], ["session_update_drafts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["campaign_entities.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_id", "candidate_id", name="uq_provenance_draft_candidate"
        ),
    )
    op.create_index(
        "ix_campaign_entity_provenance_id", "campaign_entity_provenance", ["id"]
    )
    op.create_index(
        "ix_campaign_entity_provenance_entity_id",
        "campaign_entity_provenance",
        ["entity_id"],
    )
    op.create_index(
        "ix_campaign_entity_provenance_draft_id",
        "campaign_entity_provenance",
        ["draft_id"],
    )
    op.create_index(
        "ix_campaign_entity_provenance_source_hash",
        "campaign_entity_provenance",
        ["source_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campaign_entity_provenance_source_hash",
        table_name="campaign_entity_provenance",
    )
    op.drop_index(
        "ix_campaign_entity_provenance_draft_id",
        table_name="campaign_entity_provenance",
    )
    op.drop_index(
        "ix_campaign_entity_provenance_entity_id",
        table_name="campaign_entity_provenance",
    )
    op.drop_index(
        "ix_campaign_entity_provenance_id", table_name="campaign_entity_provenance"
    )
    op.drop_table("campaign_entity_provenance")
