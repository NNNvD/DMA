from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index
from datetime import datetime, timezone
from backend.models.base import Base


class Document(Base):
    """Generic RAG document for DMA (rules, notes, lore, logs)."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # Classification and source
    kind = Column(String(50), nullable=False, index=True)  # e.g., 'rule', 'npc', 'session_log'
    source_name = Column(String(255), nullable=True)  # e.g., 'PHB', 'DM Notes', 'Homebrew'

    # Content
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)

    # URL/path if applicable
    url = Column(String(500), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Vector embedding for retrieval
    embedding = Column(JSON, nullable=True)  # JSON array of floats

    __table_args__ = (
        Index("idx_documents_kind_title", "kind", "title"),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, kind={self.kind}, title={self.title[:40]!r})>"

