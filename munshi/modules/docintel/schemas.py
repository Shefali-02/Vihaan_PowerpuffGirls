"""Typed extraction output (what the LLM must return) and its conversion to rules-engine facts."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from modules.ledger.money import rupees_to_paise
from modules.rules.service import InvoiceFacts, InvoiceLineFacts

REQUIRED_CONF_FIELDS = ("invoice_no", "invoice_date", "total", "lines")


class ExtractedLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    hsn_sac: str | None = None
    taxable_value: str
    gst_rate_pct: str | None = None
    category: str | None = None


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_no: str | None
    invoice_date: str | None
    seller_name: str | None = None
    seller_gstin: str | None
    buyer_name: str | None = None
    buyer_gstin: str | None
    place_of_supply: str | None = None
    category: str | None = None
    lines: list[ExtractedLine]
    tax_total: str | None = None
    total: str | None
    confidence: dict[str, float] = Field(default_factory=dict)

    def min_confidence(self) -> float:
        fields = list(REQUIRED_CONF_FIELDS) + (["seller_gstin"] if self.seller_gstin else []) \
            + (["buyer_gstin"] if self.buyer_gstin else [])
        return min(self.confidence.get(f, 0.0) for f in fields)

    def classify(self, workspace_gstin: str) -> tuple[str, str | None, str | None]:
        """(doc_type, counterparty_gstin, counterparty_name) relative to this workspace."""
        ours = workspace_gstin.upper()
        if (self.seller_gstin or "").upper() == ours:
            return "sale_invoice", self.buyer_gstin, self.buyer_name
        if (self.buyer_gstin or "").upper() == ours:
            return "purchase_invoice", self.seller_gstin, self.seller_name
        return "unknown", None, None

    def to_facts(self, workspace_gstin: str) -> InvoiceFacts:
        doc_type, cp_gstin, cp_name = self.classify(workspace_gstin)
        return InvoiceFacts(
            doc_type=doc_type, invoice_no=self.invoice_no or "", invoice_date=date.fromisoformat(self.invoice_date),
            counterparty_name=cp_name or "", counterparty_gstin=(cp_gstin or None),
            place_of_supply=self.place_of_supply, category=self.category,
            lines=[InvoiceLineFacts(description=ln.description, hsn_sac=ln.hsn_sac,
                                    taxable_paise=rupees_to_paise(ln.taxable_value),
                                    gst_rate_bp=rupees_to_paise(ln.gst_rate_pct) if ln.gst_rate_pct else None,
                                    category=ln.category) for ln in self.lines],
            declared_total_paise=rupees_to_paise(self.total) if self.total else None,
        )


def schema_errors(data: dict) -> list[str]:
    try:
        InvoiceExtraction.model_validate(data)
        return []
    except ValidationError as e:
        return [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
