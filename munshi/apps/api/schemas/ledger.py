from __future__ import annotations

from pydantic import BaseModel

from modules.rules.service import InvoiceFacts  # request body for drafts = engine input

__all__ = ["InvoiceFacts", "JournalLineOut", "JournalOut", "PeriodOut", "PnlRow", "PnlOut"]


class JournalLineOut(BaseModel):
    line_no: int
    account_code: str
    debit_paise: int
    credit_paise: int
    tax_tag: str | None
    memo: str


class JournalOut(BaseModel):
    id: str
    status: str
    entry_date: str
    narration: str
    period_id: str
    doc_type: str | None
    source_document_id: str | None
    ruleset_version: str | None
    supply_type: str | None
    needs_review: bool
    review_reasons: list[str]
    hints: list[str]
    lines: list[JournalLineOut]
    total_paise: int
    total: str
    created_by: str
    posted_by: str | None
    posted_at: str | None
    reverses_entry_id: str | None


class PeriodOut(BaseModel):
    id: str
    name: str
    start_date: str
    end_date: str
    status: str
    locked_at: str | None
    locked_by: str | None


class PnlRow(BaseModel):
    code: str
    name: str
    amount_paise: int
    amount: str


class PnlOut(BaseModel):
    period_id: str
    income: list[PnlRow]
    expenses: list[PnlRow]
    total_income_paise: int
    total_expenses_paise: int
    net_profit_paise: int
    total_income: str
    total_expenses: str
    net_profit: str
