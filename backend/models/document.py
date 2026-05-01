from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.chunk import DocumentChunk


class Document(Base):
    """Generic RAG document for DMA (rules, notes, lore, logs)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Classification and source
    kind: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # e.g., 'rule', 'npc', 'session_log'
    source_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # e.g., 'PHB', 'DM Notes', 'Homebrew'
    source_class: Mapped[str] = mapped_column(
        String(32), nullable=False, default="private_local", index=True
    )
    privacy_scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default="private_local"
    )
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="approved", index=True
    )
    visibility_scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default="gm_only", index=True
    )
    rag_eligible: Mapped[bool] = mapped_column(nullable=False, default=True)
    train_eligible: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Content
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # URL/path if applicable
    url: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Vector embedding for retrieval
    embedding: Mapped[list[float] | None] = mapped_column(
        JSON, nullable=True
    )  # JSON array of floats

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_documents_kind_title", "kind", "title"),
        Index(
            "idx_documents_kind_rag_visibility",
            "kind",
            "rag_eligible",
            "visibility_scope",
        ),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, kind={self.kind}, title={self.title[:40]!r})>"
