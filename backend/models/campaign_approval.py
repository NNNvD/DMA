"""Operator approval receipts; never editable through generic context tools."""

from sqlalchemy import JSON, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class CampaignApproval(Base):
    __tablename__ = "campaign_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    intent: Mapped[dict] = mapped_column(JSON, nullable=False)
    intent_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_key: Mapped[str | None] = mapped_column(String(64))
    request_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    operator_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
    approved_at: Mapped[float | None] = mapped_column(Float)
    completed_at: Mapped[float | None] = mapped_column(Float)
    result: Mapped[dict | None] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": revision}
    __table_args__ = (
        UniqueConstraint("scope_key", "request_key", name="uq_approval_request"),
    )
