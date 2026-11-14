from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin


class GstRate(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    """DB mirror of packages/rules/tables/gst_rates.yaml (effective-dated). workspace_id '*' = global default."""

    __tablename__ = "gst_rates"
    __table_args__ = (UniqueConstraint("workspace_id", "hsn_sac", "effective_from"),)
    hsn_sac: Mapped[str] = mapped_column(String(10), index=True)
    rate_bp: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(String(200), default="")
    source_version: Mapped[str] = mapped_column(String(40))
