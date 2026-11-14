"""Transactional outbox: events are written in the same DB transaction as the change."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin


class OutboxEvent(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "outbox"
    topic: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def emit(session: Session, workspace_id: str, topic: str, payload: dict[str, Any]) -> OutboxEvent:
    ev = OutboxEvent(workspace_id=workspace_id, topic=topic, payload=payload)
    session.add(ev)
    return ev
