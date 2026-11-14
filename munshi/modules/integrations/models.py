from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin


class IntegrationConnection(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "integration_connections"
    provider: Mapped[str] = mapped_column(String(20))  # GST | ITD | MCA | EPFO | NSWS | AA
    mode: Mapped[str] = mapped_column(String(10), default="MOCK")  # MOCK | LIVE
    status: Mapped[str] = mapped_column(String(20), default="MOCK_CONNECTED")
