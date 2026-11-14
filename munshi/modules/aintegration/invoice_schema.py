"""
Pydantic models for invoice extraction.

The LLM returns every field as {"value": ..., "confidence": 0..1}. Anything that
does not match raises a pydantic ValidationError, which the extractor turns into
a manual-review route (never a silent guess).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class DocumentType(str, Enum):
    purchase_invoice = "purchase_invoice"
    sales_invoice = "sales_invoice"
    credit_note = "credit_note"
    bank_statement = "bank_statement"
    other = "other"


INVOICE_TYPES = {DocumentType.purchase_invoice, DocumentType.sales_invoice}


# ---------------------------------------------------------------- helpers
def to_decimal(v: Any) -> Optional[Decimal]:
    if v is None or isinstance(v, Decimal):
        return v
    if isinstance(v, bool):
        raise ValueError("not a number")
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    if isinstance(v, str):
        s = re.sub(r"(?i)[₹,\s]|rs\.?|inr", "", v)
        if s == "":
            return None
        try:
            return Decimal(s)
        except InvalidOperation:
            raise ValueError(f"not a number: {v!r}")
    raise ValueError(f"not a number: {v!r}")


_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y", "%d %B %Y")


def parse_date(v: Any) -> Optional[date]:
    if v is None or isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    raise ValueError(f"unrecognised or invalid date: {v!r}")   # e.g. 31-02-2026


def num(d: Optional[Decimal]) -> Union[int, float, None]:
    """Decimal -> JSON number (int when whole)."""
    if d is None:
        return None
    return int(d) if d == d.to_integral_value() else float(d)


# ------------------------------------------------------------ scored fields
class _Scored(BaseModel):
    model_config = ConfigDict(extra="ignore")
    confidence: float = Field(ge=0.0, le=1.0)


class ScoredStr(_Scored):
    value: Optional[str] = None

    @field_validator("value", mode="before")
    @classmethod
    def _clean(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


class ScoredDate(_Scored):
    value: Optional[date] = None

    @field_validator("value", mode="before")
    @classmethod
    def _parse(cls, v: Any) -> Optional[date]:
        return parse_date(v)


class ScoredMoney(_Scored):
    value: Optional[Decimal] = None

    @field_validator("value", mode="before")
    @classmethod
    def _parse(cls, v: Any) -> Optional[Decimal]:
        return to_decimal(v)

    @field_serializer("value")
    def _ser(self, v: Optional[Decimal]) -> Union[int, float, None]:
        return num(v)


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str = ""
    hsn_sac: Optional[str] = None
    taxable_amount: Decimal
    gst_rate: Decimal = Field(ge=0, le=100)

    @field_validator("taxable_amount", "gst_rate", mode="before")
    @classmethod
    def _parse(cls, v: Any) -> Optional[Decimal]:
        return to_decimal(v)

    @field_serializer("taxable_amount", "gst_rate")
    def _ser(self, v: Decimal) -> Union[int, float, None]:
        return num(v)


class Classification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class ExtractedInvoice(BaseModel):
    """Issuer = vendor_*. For a purchase invoice that is the supplier; for a sales
    invoice it is the business itself and buyer_* is the customer."""
    model_config = ConfigDict(extra="ignore")

    vendor_name: Optional[ScoredStr] = None
    vendor_gstin: Optional[ScoredStr] = None
    buyer_name: Optional[ScoredStr] = None
    buyer_gstin: Optional[ScoredStr] = None
    invoice_number: Optional[ScoredStr] = None
    invoice_date: Optional[ScoredDate] = None
    items: list[LineItem] = Field(default_factory=list)
    taxable_amount: Optional[ScoredMoney] = None
    cgst: Optional[ScoredMoney] = None
    sgst: Optional[ScoredMoney] = None
    igst: Optional[ScoredMoney] = None
    total_amount: Optional[ScoredMoney] = None
    currency: Optional[ScoredStr] = None

    # -- convenience accessors (missing value -> None) --------------------
    def val(self, name: str):
        f = getattr(self, name)
        return f.value if f is not None else None

    def amount(self, name: str) -> Decimal:
        """Missing tax lines count as zero (an IGST-only invoice has no CGST/SGST)."""
        return self.val(name) or Decimal("0")

    def confidences(self) -> dict[str, float]:
        return {n: getattr(self, n).confidence for n in SCORED_FIELDS if getattr(self, n) is not None}

    def to_flat(self, document_type: DocumentType) -> dict:
        """Flat shape from the task brief (values only; confidences via .confidences())."""
        def v(n):
            x = self.val(n)
            return num(x) if isinstance(x, Decimal) else (x.isoformat() if isinstance(x, date) else x)
        return {
            "document_type": document_type.value,
            "vendor_name": v("vendor_name"), "vendor_gstin": v("vendor_gstin"),
            "buyer_name": v("buyer_name"), "buyer_gstin": v("buyer_gstin"),
            "invoice_number": v("invoice_number"), "invoice_date": v("invoice_date"),
            "items": [i.model_dump(mode="json") for i in self.items],
            "taxable_amount": v("taxable_amount"), "cgst": v("cgst"), "sgst": v("sgst"),
            "igst": v("igst"), "total_amount": v("total_amount"), "currency": v("currency") or "INR",
        }


SCORED_FIELDS = ["vendor_name", "vendor_gstin", "buyer_name", "buyer_gstin", "invoice_number",
                 "invoice_date", "taxable_amount", "cgst", "sgst", "igst", "total_amount", "currency"]


# ------------------------------------------- JSON schemas sent via the gateway
def _scored() -> dict:
    return {"type": "object", "required": ["value", "confidence"],
            "properties": {"confidence": {"type": "number"}}}


CLASSIFICATION_JSON_SCHEMA = {
    "type": "object", "required": ["document_type", "confidence"],
    "properties": {"document_type": {"type": "string", "enum": [t.value for t in DocumentType]},
                   "confidence": {"type": "number"}, "reason": {"type": "string"}},
}

EXTRACTION_JSON_SCHEMA = {
    "type": "object",
    "required": ["vendor_name", "invoice_number", "invoice_date", "taxable_amount", "total_amount"],
    "properties": {**{n: _scored() for n in SCORED_FIELDS},
                   "items": {"type": "array", "items": {"type": "object",
                             "required": ["taxable_amount", "gst_rate"]}}},
}
