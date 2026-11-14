"""Ledger tables + ORM immutability guards for posted journals."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (JSON, BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String,
                        UniqueConstraint, event, select)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin
from core.errors import ImmutableRecord


class Account(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "code"),
        CheckConstraint("type IN ('ASSET','LIABILITY','EQUITY','INCOME','EXPENSE')", name="ck_account_type"),
    )
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(10))
    tax_tag: Mapped[str | None] = mapped_column(String(30), nullable=True)


class Period(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "periods"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name"),
        CheckConstraint("status IN ('OPEN','LOCKED')", name="ck_period_status"),
    )
    name: Mapped[str] = mapped_column(String(20))  # e.g. FY2026-27
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="OPEN")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class JournalEntry(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "journal_entries"
    __table_args__ = (CheckConstraint("status IN ('DRAFT','POSTED')", name="ck_entry_status"),)
    period_id: Mapped[str] = mapped_column(ForeignKey("periods.id"), index=True)
    entry_date: Mapped[date] = mapped_column(Date)
    narration: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), default="DRAFT", index=True)
    doc_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    input_facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # engine input, re-run at post
    ruleset_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    supply_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reasons: Mapped[list] = mapped_column(JSON, default=list)
    hints: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(36))
    posted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reverses_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", order_by="JournalLine.line_no", cascade="save-update, merge", lazy="selectin"
    )


class JournalLine(Base, IdMixin, WorkspaceMixin):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint(
            "(debit_paise > 0 AND credit_paise = 0) OR (credit_paise > 0 AND debit_paise = 0)",
            name="ck_line_one_side",
        ),
    )
    entry_id: Mapped[str] = mapped_column(ForeignKey("journal_entries.id"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    account_code: Mapped[str] = mapped_column(String(10), index=True)
    debit_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    credit_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    tax_tag: Mapped[str | None] = mapped_column(String(30), nullable=True)
    memo: Mapped[str] = mapped_column(String(300), default="")
    entry: Mapped[JournalEntry] = relationship(back_populates="lines")


# ---- immutability guards (Postgres also has triggers, see core/db.py) -------------
@event.listens_for(JournalEntry, "before_update")
def _guard_entry_update(mapper, connection, target: JournalEntry):
    from sqlalchemy import inspect

    hist = inspect(target).attrs.status.history
    previous = hist.deleted[0] if hist.deleted else target.status
    if previous == "POSTED":
        raise ImmutableRecord("Posted journal entries cannot be modified; post a reversal")


@event.listens_for(JournalEntry, "before_delete")
def _guard_entry_delete(mapper, connection, target: JournalEntry):
    if target.status == "POSTED":
        raise ImmutableRecord("Posted journal entries cannot be deleted; post a reversal")


def _entry_posted(connection, entry_id: str) -> bool:
    status = connection.execute(select(JournalEntry.status).where(JournalEntry.id == entry_id)).scalar()
    return status == "POSTED"


@event.listens_for(JournalLine, "before_update")
def _guard_line_update(mapper, connection, target: JournalLine):
    if _entry_posted(connection, target.entry_id):
        raise ImmutableRecord("Lines of a posted journal cannot be modified")


@event.listens_for(JournalLine, "before_delete")
def _guard_line_delete(mapper, connection, target: JournalLine):
    if _entry_posted(connection, target.entry_id):
        raise ImmutableRecord("Lines of a posted journal cannot be deleted")
