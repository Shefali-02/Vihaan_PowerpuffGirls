"""Ledger queries. Every query filters by workspace_id."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.ledger.models import Account, JournalEntry, JournalLine, Period


def accounts(s: Session, ws: str) -> list[Account]:
    return list(s.scalars(select(Account).where(Account.workspace_id == ws).order_by(Account.code)))


def periods(s: Session, ws: str) -> list[Period]:
    return list(s.scalars(select(Period).where(Period.workspace_id == ws).order_by(Period.start_date)))


def period(s: Session, ws: str, period_id: str) -> Period | None:
    return s.scalar(select(Period).where(Period.workspace_id == ws, Period.id == period_id))


def period_for_date(s: Session, ws: str, on: date) -> Period | None:
    return s.scalar(select(Period).where(Period.workspace_id == ws, Period.start_date <= on, Period.end_date >= on))


def entry(s: Session, ws: str, entry_id: str) -> JournalEntry | None:
    return s.scalar(select(JournalEntry).where(JournalEntry.workspace_id == ws, JournalEntry.id == entry_id))


def reversal_of(s: Session, ws: str, entry_id: str) -> JournalEntry | None:
    return s.scalar(select(JournalEntry).where(JournalEntry.workspace_id == ws,
                                               JournalEntry.reverses_entry_id == entry_id))


def account_totals(s: Session, ws: str, period_id: str) -> list[tuple[str, int, int]]:
    """(account_code, total_debit, total_credit) over POSTED entries in the period."""
    stmt = (
        select(JournalLine.account_code, func.coalesce(func.sum(JournalLine.debit_paise), 0),
               func.coalesce(func.sum(JournalLine.credit_paise), 0))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalLine.workspace_id == ws, JournalEntry.workspace_id == ws,
               JournalEntry.period_id == period_id, JournalEntry.status == "POSTED")
        .group_by(JournalLine.account_code)
        .order_by(JournalLine.account_code)
    )
    return [(c, int(d), int(cr)) for c, d, cr in s.execute(stmt)]


def tag_totals(s: Session, ws: str, period_id: str) -> list[tuple[str, int, int]]:
    stmt = (
        select(JournalLine.tax_tag, func.coalesce(func.sum(JournalLine.debit_paise), 0),
               func.coalesce(func.sum(JournalLine.credit_paise), 0))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalLine.workspace_id == ws, JournalEntry.workspace_id == ws,
               JournalEntry.period_id == period_id, JournalEntry.status == "POSTED",
               JournalLine.tax_tag.is_not(None))
        .group_by(JournalLine.tax_tag)
    )
    return [(t, int(d), int(c)) for t, d, c in s.execute(stmt)]


def count_entries(s: Session, ws: str, period_id: str, status: str) -> int:
    return int(s.scalar(select(func.count()).select_from(JournalEntry).where(
        JournalEntry.workspace_id == ws, JournalEntry.period_id == period_id, JournalEntry.status == status)) or 0)
