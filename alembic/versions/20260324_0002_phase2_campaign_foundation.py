"""phase 2 campaign foundation

Revision ID: 20260324_0002
Revises: 20260310_0001
Create Date: 2026-03-24 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260324_0002"
down_revision = "20260310_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stable_key", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("parent_entity_id", sa.Integer(), nullable=True),
        sa.Column("current_location_id", sa.Integer(), nullable=True),
        sa.Column("owner_entity_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["current_location_id"],
            ["campaign_entities.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_entity_id"],
            ["campaign_entities.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_entity_id"],
            ["campaign_entities.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_campaign_entities_id", "campaign_entities", ["id"], unique=False
    )
    op.create_index(
        "ix_campaign_entities_stable_key",
        "campaign_entities",
        ["stable_key"],
        unique=True,
    )
    op.create_index(
        "ix_campaign_entities_entity_type",
        "campaign_entities",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_entities_name", "campaign_entities", ["name"], unique=False
    )
    op.create_index(
        "ix_campaign_entities_parent_entity_id",
        "campaign_entities",
        ["parent_entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_entities_current_location_id",
        "campaign_entities",
        ["current_location_id"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_entities_owner_entity_id",
        "campaign_entities",
        ["owner_entity_id"],
        unique=False,
    )
    op.create_index(
        "idx_campaign_entities_type_name",
        "campaign_entities",
        ["entity_type", "name"],
        unique=False,
    )
    op.create_index(
        "idx_campaign_entities_active_type",
        "campaign_entities",
        ["is_active", "entity_type"],
        unique=False,
    )

    op.create_table(
        "campaign_relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_entity_id", sa.Integer(), nullable=False),
        sa.Column("target_entity_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("strength", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_entity_id"], ["campaign_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"], ["campaign_entities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_campaign_relationships_pair_type",
        ),
    )
    op.create_index(
        "ix_campaign_relationships_id", "campaign_relationships", ["id"], unique=False
    )
    op.create_index(
        "ix_campaign_relationships_source_entity_id",
        "campaign_relationships",
        ["source_entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_relationships_target_entity_id",
        "campaign_relationships",
        ["target_entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_relationships_relationship_type",
        "campaign_relationships",
        ["relationship_type"],
        unique=False,
    )

    op.create_table(
        "character_sheet_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["campaign_entities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_id",
            "version_number",
            name="uq_character_sheet_versions_entity_version",
        ),
    )
    op.create_index(
        "ix_character_sheet_versions_id",
        "character_sheet_versions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_character_sheet_versions_entity_id",
        "character_sheet_versions",
        ["entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_character_sheet_versions_entity_id", table_name="character_sheet_versions"
    )
    op.drop_index(
        "ix_character_sheet_versions_id", table_name="character_sheet_versions"
    )
    op.drop_table("character_sheet_versions")

    op.drop_index(
        "ix_campaign_relationships_relationship_type",
        table_name="campaign_relationships",
    )
    op.drop_index(
        "ix_campaign_relationships_target_entity_id",
        table_name="campaign_relationships",
    )
    op.drop_index(
        "ix_campaign_relationships_source_entity_id",
        table_name="campaign_relationships",
    )
    op.drop_index("ix_campaign_relationships_id", table_name="campaign_relationships")
    op.drop_table("campaign_relationships")

    op.drop_index("idx_campaign_entities_active_type", table_name="campaign_entities")
    op.drop_index("idx_campaign_entities_type_name", table_name="campaign_entities")
    op.drop_index(
        "ix_campaign_entities_owner_entity_id", table_name="campaign_entities"
    )
    op.drop_index(
        "ix_campaign_entities_current_location_id", table_name="campaign_entities"
    )
    op.drop_index(
        "ix_campaign_entities_parent_entity_id", table_name="campaign_entities"
    )
    op.drop_index("ix_campaign_entities_name", table_name="campaign_entities")
    op.drop_index("ix_campaign_entities_entity_type", table_name="campaign_entities")
    op.drop_index("ix_campaign_entities_stable_key", table_name="campaign_entities")
    op.drop_index("ix_campaign_entities_id", table_name="campaign_entities")
    op.drop_table("campaign_entities")
