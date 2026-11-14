from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin


class Document(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "documents"
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    duplicate_of: Mapped[str | None] = mapped_column(String(36), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(36))


class Extraction(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "extractions"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    ai_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    llm_mode: Mapped[str] = mapped_column(String(10))
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid: Mapped[bool] = mapped_column(Boolean, default=False)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    dedupe_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class Proposal(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    """What the AI proposed for a document and how it was routed. Never a journal itself."""

    __tablename__ = "proposals"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    extraction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    draft_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ruleset_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    llm_mode: Mapped[str] = mapped_column(String(10))
    doc_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    total_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
