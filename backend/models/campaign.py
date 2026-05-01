from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class CampaignEntity(Base):
    __tablename__ = "campaign_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stable_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    parent_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaign_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaign_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    owner_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaign_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    parent_entity: Mapped["CampaignEntity | None"] = relationship(
        "CampaignEntity",
        remote_side="CampaignEntity.id",
        foreign_keys=[parent_entity_id],
        lazy="joined",
    )
    current_location: Mapped["CampaignEntity | None"] = relationship(
        "CampaignEntity",
        remote_side="CampaignEntity.id",
        foreign_keys=[current_location_id],
        lazy="joined",
    )
    owner_entity: Mapped["CampaignEntity | None"] = relationship(
        "CampaignEntity",
        remote_side="CampaignEntity.id",
        foreign_keys=[owner_entity_id],
        lazy="joined",
    )
    outgoing_relationships: Mapped[list["CampaignRelationship"]] = relationship(
        "CampaignRelationship",
        foreign_keys="CampaignRelationship.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incoming_relationships: Mapped[list["CampaignRelationship"]] = relationship(
        "CampaignRelationship",
        foreign_keys="CampaignRelationship.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sheet_versions: Mapped[list["CharacterSheetVersion"]] = relationship(
        "CharacterSheetVersion",
        back_populates="entity",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CharacterSheetVersion.version_number",
    )

    __table_args__ = (
        Index("idx_campaign_entities_type_name", "entity_type", "name"),
        Index("idx_campaign_entities_active_type", "is_active", "entity_type"),
    )


class CampaignRelationship(Base):
    __tablename__ = "campaign_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_entity_id: Mapped[int] = mapped_column(
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[int] = mapped_column(
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    source_entity: Mapped["CampaignEntity"] = relationship(
        "CampaignEntity",
        foreign_keys=[source_entity_id],
        back_populates="outgoing_relationships",
        lazy="joined",
    )
    target_entity: Mapped["CampaignEntity"] = relationship(
        "CampaignEntity",
        foreign_keys=[target_entity_id],
        back_populates="incoming_relationships",
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_campaign_relationships_pair_type",
        ),
    )


class CharacterSheetVersion(Base):
    __tablename__ = "character_sheet_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    entity: Mapped["CampaignEntity"] = relationship(
        "CampaignEntity",
        back_populates="sheet_versions",
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "version_number",
            name="uq_character_sheet_versions_entity_version",
        ),
    )
