from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    JSON,
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CampaignEntity(Base):
    __tablename__ = "campaign_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    pc_detail: Mapped["CampaignPC | None"] = relationship(
        "CampaignPC",
        back_populates="entity",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    npc_detail: Mapped["CampaignNPC | None"] = relationship(
        "CampaignNPC",
        back_populates="entity",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    faction_detail: Mapped["CampaignFaction | None"] = relationship(
        "CampaignFaction",
        back_populates="entity",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    location_detail: Mapped["CampaignLocation | None"] = relationship(
        "CampaignLocation",
        back_populates="entity",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    event_detail: Mapped["CampaignEvent | None"] = relationship(
        "CampaignEvent",
        back_populates="entity",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    outgoing_relationships: Mapped[list["CampaignRelationship"]] = relationship(
        "CampaignRelationship",
        back_populates="from_entity",
        foreign_keys="CampaignRelationship.from_entity_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incoming_relationships: Mapped[list["CampaignRelationship"]] = relationship(
        "CampaignRelationship",
        back_populates="to_entity",
        foreign_keys="CampaignRelationship.to_entity_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (Index("idx_campaign_entities_type_name", "entity_type", "name"),)


class CampaignPC(Base):
    __tablename__ = "campaign_pcs"

    entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ancestry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    character_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    background: Mapped[str | None] = mapped_column(String(255), nullable=True)
    backstory: Mapped[str | None] = mapped_column(Text, nullable=True)
    homeland: Mapped[str | None] = mapped_column(String(255), nullable=True)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    notable_items: Mapped[list[str]] = mapped_column(JSON, default=list)

    entity: Mapped[CampaignEntity] = relationship(
        "CampaignEntity", back_populates="pc_detail"
    )


class CampaignNPC(Base):
    __tablename__ = "campaign_npcs"

    entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(100), nullable=True)

    entity: Mapped[CampaignEntity] = relationship(
        "CampaignEntity", back_populates="npc_detail"
    )


class CampaignFaction(Base):
    __tablename__ = "campaign_factions"

    entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    influence: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alignment: Mapped[str | None] = mapped_column(String(100), nullable=True)

    entity: Mapped[CampaignEntity] = relationship(
        "CampaignEntity", back_populates="faction_detail"
    )


class CampaignLocation(Base):
    __tablename__ = "campaign_locations"

    entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    location_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(100), nullable=True)

    entity: Mapped[CampaignEntity] = relationship(
        "CampaignEntity", back_populates="location_detail"
    )


class CampaignEvent(Base):
    __tablename__ = "campaign_events"

    entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    event_date: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phase: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    entity: Mapped[CampaignEntity] = relationship(
        "CampaignEntity", back_populates="event_detail"
    )


class CampaignRelationship(Base):
    __tablename__ = "campaign_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    from_entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        index=True,
    )
    to_entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaign_entities.id", ondelete="CASCADE"),
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(80), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campaign_imports.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    from_entity: Mapped[CampaignEntity] = relationship(
        "CampaignEntity",
        back_populates="outgoing_relationships",
        foreign_keys=[from_entity_id],
    )
    to_entity: Mapped[CampaignEntity] = relationship(
        "CampaignEntity",
        back_populates="incoming_relationships",
        foreign_keys=[to_entity_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "from_entity_id",
            "to_entity_id",
            "relationship_type",
            name="uq_campaign_relationship_unique_edge",
        ),
        Index(
            "idx_campaign_relationship_from_type",
            "from_entity_id",
            "relationship_type",
        ),
        Index(
            "idx_campaign_relationship_to_type",
            "to_entity_id",
            "relationship_type",
        ),
    )


class CampaignImport(Base):
    __tablename__ = "campaign_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_kind: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(50), default="applied")
    entity_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    relationship_specs: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    last_result: Mapped[dict[str, int | str] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "source_kind",
            "source_id",
            name="uq_campaign_import_source",
        ),
    )
