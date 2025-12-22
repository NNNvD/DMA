from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Text, Index
from sqlalchemy.orm import Mapped, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.document import Document


class DocumentChunk(Base):
    """Chunked document content optimized for retrieval."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (Index("idx_document_chunks_doc_idx", "document_id", "chunk_index"),)
