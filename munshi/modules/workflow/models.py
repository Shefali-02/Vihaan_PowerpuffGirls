from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin


class Approval(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint("object_type IN ('journal','period_close','investor_pack')", name="ck_approval_object"),
    )
    object_type: Mapped[str] = mapped_column(String(20))
    object_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(20), index=True)
    risk: Mapped[str] = mapped_column(String(10))  # LOW | HIGH
    version_hash: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    requested_by: Mapped[str] = mapped_column(String(36))
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_batch: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Comment(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "comments"
    approval_id: Mapped[str] = mapped_column(ForeignKey("approvals.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36))
    body: Mapped[str] = mapped_column(Text)
