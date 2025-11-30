from sqlalchemy import Column, Integer, String, JSON, DateTime, Index
from datetime import datetime, timezone
from backend.models.base import Base


class ContextEntry(Base):
    __tablename__ = "contexts"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(200), unique=True, index=True, nullable=False)
    data = Column(JSON, nullable=False)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (Index("idx_contexts_key", "key"),)

