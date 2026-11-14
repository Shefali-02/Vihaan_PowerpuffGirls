"""Rules engine value objects (no DB tables: rules live in packages/rules YAML)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

DocType = Literal["purchase_invoice", "sale_invoice"]


class InvoiceLineFacts(BaseModel):
    description: str = ""
    hsn_sac: str | None = None
    taxable_paise: int = Field(..., description="Taxable value in integer paise")
    gst_rate_bp: int | None = Field(None, description="GST rate in basis points (1800 = 18%); None -> HSN table")
    category: str | None = None


class InvoiceFacts(BaseModel):
    """Normalised invoice facts: the only input the rules engine accepts."""

    doc_type: DocType
    invoice_no: str
    invoice_date: date
    counterparty_name: str = ""
    counterparty_gstin: str | None = None
    place_of_supply: str | None = Field(None, description="2-digit state code; defaults from GSTINs")
    category: str | None = None
    lines: list[InvoiceLineFacts]
    declared_total_paise: int | None = None


@dataclass(frozen=True)
class TaxContext:
    workspace_gstin: str
    workspace_state: str


@dataclass(frozen=True)
class DraftLine:
    account_code: str
    debit_paise: int
    credit_paise: int
    tax_tag: str | None = None
    memo: str = ""

    def key(self) -> tuple:
        return (self.account_code, self.debit_paise, self.credit_paise, self.tax_tag or "")


@dataclass
class DraftJournal:
    doc_type: str
    entry_date: date
    narration: str
    lines: list[DraftLine]
    ruleset_id: str
    ruleset_version: str
    supply_type: str  # INTRA | INTER
    total_paise: int
    tax_paise: int
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    explanation: list[dict] = field(default_factory=list)

    @property
    def total_debit(self) -> int:
        return sum(line.debit_paise for line in self.lines)

    @property
    def total_credit(self) -> int:
        return sum(line.credit_paise for line in self.lines)

    @property
    def balanced(self) -> bool:
        return self.total_debit == self.total_credit and self.total_debit > 0


@dataclass
class Rejection:
    reasons: list[dict]
    code: str = "RULE_REJECTED"
    ruleset_version: str | None = None
