from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, IdMixin, TimestampMixin


class Workspace(Base, IdMixin, TimestampMixin):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(200))
    gstin: Mapped[str] = mapped_column(String(15))
    state_code: Mapped[str] = mapped_column(String(2))
    pan: Mapped[str] = mapped_column(String(10))

    @property
    def workspace_id(self) -> str:  # a workspace is its own scope
        return self.id


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    # CA registration number: captured for display only, never verified against ICAI.
    ca_reg_no: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Membership(Base, IdMixin, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        CheckConstraint("role IN ('ACCOUNTANT','CA','INVESTOR')", name="ck_membership_role"),
    )
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
