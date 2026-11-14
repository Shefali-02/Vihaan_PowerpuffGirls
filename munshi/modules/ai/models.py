from __future__ import annotations

from sqlalchemy import JSON, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin


class AiRun(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    """One row per LLM call through the gateway (inputs are hashed, never stored raw)."""

    __tablename__ = "ai_runs"
    prompt_id: Mapped[str] = mapped_column(String(80), index=True)
    llm_mode: Mapped[str] = mapped_column(String(10))  # MOCK | PRUNE
    model: Mapped[str] = mapped_column(String(80))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20))  # OK | ERROR | INVALID_SCHEMA
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    repaired: Mapped[bool] = mapped_column(default=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    redactions: Mapped[dict] = mapped_column(JSON, default=dict)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
